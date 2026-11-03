// Read-only metadata reporter for an explicitly selected MGSV test copy.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/unknown321/hashing"
)

type archiveInfo struct {
	Name, Status string
	Bytes        int64
	Version      uint32
	Entries      int
}
type containerInfo struct {
	Archive, Path, Parent, Hash, Status string
	ChecksumStage                       string
	Entry                               uint32
	Depth                               int
	Metadata                            *packMetadata
}
type probe struct {
	Path, Basis string
	Matches     int
}
type report struct {
	Kind, Version, ExecutableSHA256 string
	ReadOnly, EnumerationFinished   bool
	Archives                        []archiveInfo
	Probes                          []probe
	Containers                      []containerInfo
	LimitSkips, ParseFailures       int
	Limitations                     []string
}
type source struct {
	file *os.File
	info archiveInfo
}
type occurrence struct {
	archive int
	entry   archiveEntry
}

var progress io.Writer = io.Discard

func seeds() []string {
	base := "/Assets/tpp/pack/mission2/free/"
	names := []string{"f30010/f30010", "f30010/f30011", "f30020/f30020",
		"f30050/f30050", "f30050/f30051", "f30050/f30050_Buddy",
		"f30150/f30150", "f30250/f30250"}
	for i := 0; i < 100; i++ {
		names = append(names, fmt.Sprintf("f30050/f30050_hanger_btg%02d", i))
	}
	paths := []string{}
	for _, name := range names {
		paths = append(paths, base+name+".fpk", base+name+".fpkd")
	}
	for _, name := range []string{"afgh", "mafr", "mtbs"} {
		paths = append(paths, "/Assets/tpp/pack/mission2/common/mis_com_"+name+".fpk",
			"/Assets/tpp/pack/mission2/common/mis_com_"+name+".fpkd")
	}
	return paths
}

func inside(child, parent string) bool {
	rel, err := filepath.Rel(parent, child)
	return err == nil && !filepath.IsAbs(rel) && rel != ".." &&
		!strings.HasPrefix(rel, ".."+string(filepath.Separator))
}

func collect(root string) (report, error) {
	out := report{Kind: "mgsv_pack_metadata_only_not_gameplay_validation", Version: "2",
		ReadOnly: true, Archives: []archiveInfo{}, Probes: []probe{}, Containers: []containerInfo{},
		Limitations: []string{
			"Known archive paths only; missing files are explicit. No archive load precedence is inferred.",
			"Paths are hash-matched candidates. Hanger levels 00..99 and FPKD companions are probes, not proven content.",
			"Members/references locate allocation candidates; entity counts and controller properties are not decoded.",
			"References are external packs; member bodies, keys, scripts, saves and account data are not exported.",
			"Limits: 250000 entries/archive; 1000000 total; 64MiB/container; 256MiB decoded; 64 containers; 25000 metadata records; reference depth2.",
			"Empty or partial findings do not prove an asset is absent from the game or that co-op works.",
			"Hash inputs over128bytes are listed but not resolved; EnumerationFinished can include failures/skips.",
		}}
	executable, err := os.Open(filepath.Join(root, "mgsvtpp.exe"))
	if err != nil {
		return out, fail("test_copy_executable_unreadable")
	}
	hash := sha256.New()
	count, hashErr := io.Copy(hash, io.LimitReader(executable, 512<<20+1))
	executable.Close()
	if hashErr != nil || count < 1 || count > 512<<20 {
		return out, fail("executable_hash_read_or_limit")
	}
	out.ExecutableSHA256 = hex.EncodeToString(hash.Sum(nil))
	paths := []string{"master/0/00.dat.vendor", "master/0/00.dat", "master/0/01.dat", "master/data1.dat"}
	for i := 0; i <= 4; i++ {
		paths = append(paths, fmt.Sprintf("master/chunk%d.dat", i))
	}
	sort.Strings(paths)
	sources := []source{}
	defer func() {
		for _, source := range sources {
			source.file.Close()
		}
	}()
	index := map[uint64][]occurrence{}
	totalEntries := 0
	for _, name := range paths {
		info := archiveInfo{Name: name, Status: "missing_or_unreadable"}
		full := filepath.Join(root, filepath.FromSlash(name))
		stat, err := os.Lstat(full)
		if err != nil {
			out.Archives = append(out.Archives, info)
			continue
		}
		if !stat.Mode().IsRegular() {
			info.Status = "non_regular_skipped"
			out.Archives = append(out.Archives, info)
			continue
		}
		info.Bytes = stat.Size()
		file, err := os.Open(full)
		if err != nil {
			out.Archives = append(out.Archives, info)
			continue
		}
		fmt.Fprintln(progress, "Reading archive metadata:", name)
		version, entries, parseErr := indexArchive(file, stat.Size())
		info.Version = version
		if parseErr != nil || totalEntries+len(entries) > 1000000 {
			info.Status = "total_entry_limit"
			if parseErr != nil {
				info.Status = parseErr.Error()
				out.ParseFailures++
			} else {
				out.LimitSkips++
			}
			file.Close()
			out.Archives = append(out.Archives, info)
			continue
		}
		info.Status, info.Entries = "indexed", len(entries)
		slot := len(sources)
		sources = append(sources, source{file: file, info: info})
		for _, entry := range entries {
			index[entry.hash] = append(index[entry.hash], occurrence{slot, entry})
		}
		totalEntries += len(entries)
		out.Archives = append(out.Archives, info)
	}
	type request struct {
		name, basis string
		depth       int
	}
	queue := []request{}
	queued := map[string]bool{}
	enqueue := func(name, basis string, depth int) {
		if queued[name] {
			return
		}
		if len(queued) >= 4096 {
			out.LimitSkips++
			return
		}
		queued[name] = true
		queue = append(queue, request{name, basis, depth})
	}
	for _, name := range seeds() {
		enqueue(name, "pinned_loader_or_bounded_companion_probe", 0)
	}
	seen := map[string]bool{}
	decodedTotal, records := uint64(0), 0
	fmt.Fprintln(progress, "Inspecting selected package tables...")
	var visit func([]byte, containerInfo)
	visit = func(data []byte, node containerInfo) {
		if len(out.Containers) >= maxContainers {
			out.LimitSkips++
			return
		}
		metadata, err := inspectFPK(data)
		if err != nil {
			node.Status = err.Error()
			out.ParseFailures++
			out.Containers = append(out.Containers, node)
			return
		}
		if records+len(metadata.Members)+len(metadata.References) > maxRecords {
			node.Status = "metadata_record_limit"
			out.LimitSkips++
			out.Containers = append(out.Containers, node)
			return
		}
		records += len(metadata.Members) + len(metadata.References)
		node.Status, node.Metadata = "metadata_ok", &metadata
		out.Containers = append(out.Containers, node)
		if node.Depth >= 2 {
			if len(metadata.References) > 0 {
				out.LimitSkips++
			}
			for _, item := range metadata.Members {
				if strings.HasSuffix(item.Name, ".fpk") || strings.HasSuffix(item.Name, ".fpkd") {
					out.LimitSkips++
				}
			}
			return
		}
		for _, ref := range metadata.References {
			if strings.HasSuffix(ref, ".fpk") || strings.HasSuffix(ref, ".fpkd") {
				enqueue(ref, "external_pack_reference_hash_match", node.Depth+1)
				if strings.HasSuffix(ref, ".fpk") {
					enqueue(ref+"d", "referenced_pack_companion_probe", node.Depth+1)
				}
			}
		}
		for _, item := range metadata.Members {
			if strings.HasSuffix(item.Name, ".fpk") || strings.HasSuffix(item.Name, ".fpkd") {
				child := containerInfo{Archive: node.Archive, Entry: node.Entry, Path: item.Name,
					Parent: node.Path, Depth: node.Depth + 1}
				visit(data[uint64(item.Offset):uint64(item.Offset)+uint64(item.Size)], child)
			}
		}
	}
	for cursor := 0; cursor < len(queue); cursor++ {
		req := queue[cursor]
		// The pinned CityHash implementation is verified here only up to128 bytes.
		// Avoid its unverified long-input loop; retain an explicit skipped probe.
		trimmed := strings.TrimPrefix(strings.TrimPrefix(req.name, "/Assets/"), "/")
		if dot := strings.LastIndex(trimmed, "."); dot > 0 {
			trimmed = trimmed[:dot]
		}
		if len(trimmed) > 128 {
			out.LimitSkips++
			out.Probes = append(out.Probes, probe{req.name, "hash_name_length_limit", 0})
			continue
		}
		matches := index[hashing.HashFileNameWithExtension(req.name)]
		out.Probes = append(out.Probes, probe{req.name, req.basis, len(matches)})
		for _, found := range matches {
			key := fmt.Sprintf("%d:%d", found.archive, found.entry.index)
			if seen[key] {
				continue
			}
			seen[key] = true
			src := sources[found.archive]
			node := containerInfo{Archive: src.info.Name, Path: req.name, Entry: found.entry.index,
				Hash: fmt.Sprintf("%016x", found.entry.hash), Depth: req.depth}
			if len(out.Containers) >= maxContainers || decodedTotal+uint64(found.entry.decoded) > maxTotalBytes {
				out.LimitSkips++
				continue
			}
			data, stage, err := decodeContainer(src.file, src.info.Version, found.entry)
			if err != nil {
				node.Status = err.Error()
				out.ParseFailures++
				out.Containers = append(out.Containers, node)
				continue
			}
			decodedTotal += uint64(len(data))
			node.ChecksumStage = stage
			visit(data, node)
		}
	}
	sort.Slice(out.Probes, func(i, j int) bool { return out.Probes[i].Path < out.Probes[j].Path })
	out.EnumerationFinished = true
	return out, nil
}

func run(root, output string) error {
	actualRoot, err := filepath.EvalSymlinks(root)
	if err != nil {
		return fail("test_copy_directory_unavailable")
	}
	actualRoot, err = filepath.Abs(actualRoot)
	if err != nil {
		return fail("test_copy_directory_invalid")
	}
	parent, err := filepath.EvalSymlinks(filepath.Dir(output))
	if err != nil {
		return fail("output_parent_unavailable")
	}
	parent, err = filepath.Abs(parent)
	if err != nil || inside(parent, actualRoot) {
		return fail("output_must_be_outside_game_copy")
	}
	result, err := collect(actualRoot)
	if err != nil {
		return err
	}
	data, err := json.MarshalIndent(result, "", "  ")
	if err != nil || len(data) > 16<<20 {
		return fail("report_encoding_or_size_limit")
	}
	target, err := os.OpenFile(filepath.Join(parent, filepath.Base(output)), os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return fail("output_exists_or_cannot_be_created")
	}
	_, writeErr := target.Write(append(data, '\n'))
	closeErr := target.Close()
	if writeErr != nil || closeErr != nil {
		return fail("output_write_failed")
	}
	return nil
}

func main() {
	progress = os.Stderr
	root := flag.String("game-dir", "", "explicit copied MGSV directory (read-only)")
	output := flag.String("output", "", "new JSON file outside the game copy")
	flag.Parse()
	if *root == "" || *output == "" {
		fmt.Fprintln(os.Stderr, "Specify --game-dir and --output")
		os.Exit(2)
	}
	if err := run(*root, *output); err != nil {
		fmt.Fprintln(os.Stderr, "Pack report:", err)
		os.Exit(1)
	}
	fmt.Println("Metadata report written. No game files were changed.")
}
