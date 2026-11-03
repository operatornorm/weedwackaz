package main

import (
	"bytes"
	"compress/zlib"
	"crypto/md5"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"io"
	"path"
	"strings"
	"unicode/utf8"

	"github.com/unknown321/datfpk/crypto"
	"github.com/unknown321/datfpk/fpk"
	"github.com/unknown321/datfpk/qar"
)

const (
	maxEntries    = 250000
	maxPackBytes  = 64 << 20
	maxTotalBytes = 256 << 20
	maxRecords    = 25000
	maxContainers = 64
	maxNames      = 4096
	maxNameBytes  = 512
)

var le = binary.LittleEndian

func fail(code string) error { return errors.New(code) }
func span(offset, length, total uint64) bool {
	return offset <= total && length <= total-offset
}

type archiveEntry struct {
	index, stored, decoded uint32
	hash                   uint64
	offset                 int64
	checksum               qar.Md5Sum
}

// Validate every count and span before library decryption or allocation.
func indexArchive(reader io.ReaderAt, size int64) (uint32, []archiveEntry, error) {
	if size < 32 {
		return 0, nil, fail("qar_header_truncated")
	}
	header := make([]byte, 32)
	if _, err := reader.ReadAt(header, 0); err != nil {
		return 0, nil, fail("qar_header_read")
	}
	if string(header[:4]) != "SQAR" {
		return 0, nil, fail("qar_magic")
	}
	flags := le.Uint32(header[4:]) ^ 0x41441043
	count := le.Uint32(header[8:]) ^ 0x11C22050
	version := le.Uint32(header[24:]) ^ 0x41441043
	if version != 1 && version != 2 {
		return version, nil, fail("qar_version")
	}
	tableEnd := uint64(32) + uint64(count)*8
	if count > maxEntries || tableEnd > uint64(size) {
		return version, nil, fail("qar_table_limit_or_bounds")
	}
	encoded := make([]byte, int(count)*8)
	if len(encoded) > 0 {
		if _, err := reader.ReadAt(encoded, 32); err != nil {
			return version, nil, fail("qar_section_read")
		}
	}
	sections, err := qar.DecryptSectionList(count, encoded, version, false)
	if err != nil {
		return version, nil, fail("qar_section_decode")
	}
	shift := 10
	if flags&0x800 != 0 {
		shift = 12
	}
	result := make([]archiveEntry, 0, int(count))
	for index, section := range sections {
		offset := (section >> 40) << shift
		if offset < tableEnd || !span(offset, 32, uint64(size)) {
			return version, nil, fail("qar_entry_header_bounds")
		}
		entryHeader := make([]byte, 32)
		if _, err := reader.ReadAt(entryHeader, int64(offset)); err != nil {
			return version, nil, fail("qar_entry_header_read")
		}
		entry := archiveEntry{index: uint32(index), hash: le.Uint64(entryHeader) ^ 0x4144104341441043,
			stored:  le.Uint32(entryHeader[8:]) ^ 0x11C22050,
			decoded: le.Uint32(entryHeader[12:]) ^ 0xD05608C3, offset: int64(offset) + 32}
		if !span(uint64(entry.offset), uint64(entry.stored), uint64(size)) {
			return version, nil, fail("qar_payload_bounds")
		}
		copy(entry.checksum[:], entryHeader[16:32])
		entry.checksum, err = qar.Md5Decode(entry.checksum)
		if err != nil {
			return version, nil, fail("qar_checksum_header")
		}
		result = append(result, entry)
	}
	return version, result, nil
}

func decodeContainer(reader io.ReaderAt, version uint32, entry archiveEntry) ([]byte, string, error) {
	if entry.stored < 8 || entry.stored > maxPackBytes+16 || entry.decoded > maxPackBytes+16 {
		return nil, "", fail("container_size_limit")
	}
	raw := make([]byte, int(entry.stored))
	if _, err := reader.ReadAt(raw, entry.offset); err != nil {
		return nil, "", fail("container_read")
	}
	first := qar.Decrypt1Stream{}
	first.Init(entry.checksum, entry.hash, version, len(raw))
	decoded, err := first.Read(bytes.NewReader(raw), len(raw))
	if err != nil {
		return nil, "", fail("container_outer_decode")
	}
	// datfpk writes a digest of this representation; independent compressed
	// fixtures use the final payload. Neither match can bypass full decoding.
	storedDigest := qar.Md5Sum(md5.Sum(decoded))
	magic := le.Uint32(decoded)
	headerSize := crypto.GetHeaderSize(magic)
	if len(decoded) < headerSize {
		return nil, "", fail("container_encryption_header")
	}
	innerSize := uint64(entry.decoded)
	if headerSize > 0 {
		if innerSize < uint64(headerSize) {
			return nil, "", fail("container_decoded_length")
		}
		innerSize -= uint64(headerSize)
		if magic == crypto.Magic2 {
			advertised := uint64(le.Uint32(decoded[8:]))
			if (uint64(entry.decoded) != advertised && innerSize != advertised) ||
				le.Uint32(decoded[12:]) != entry.stored-uint32(headerSize) {
				return nil, "", fail("container_inner_length")
			}
			innerSize = advertised
		}
		second := qar.Decrypt2Stream{}
		second.Init(le.Uint32(decoded[4:]))
		decoded, err = second.Decrypt2(decoded[headerSize:], len(decoded)-headerSize)
		if err != nil {
			return nil, "", fail("container_inner_decode")
		}
	}
	if innerSize > maxPackBytes {
		return nil, "", fail("container_size_limit")
	}
	if entry.stored != entry.decoded {
		input := bytes.NewReader(decoded)
		compressed, err := zlib.NewReader(input)
		if err != nil {
			return nil, "", fail("container_zlib_header")
		}
		limit := innerSize
		if magic == crypto.Magic1 {
			limit = uint64(entry.decoded)
		}
		decoded, err = io.ReadAll(io.LimitReader(compressed, int64(limit)+1))
		closeErr := compressed.Close()
		if err != nil || closeErr != nil {
			return nil, "", fail("container_zlib_read")
		}
		if input.Len() != 0 {
			return nil, "", fail("container_zlib_trailing_data")
		}
	}
	if len(decoded) > maxPackBytes || (uint64(len(decoded)) != innerSize &&
		!(magic == crypto.Magic1 && uint64(len(decoded)) == uint64(entry.decoded))) {
		return nil, "", fail("container_decoded_length")
	}
	storedMatch := storedDigest == entry.checksum
	payloadMatch := qar.Md5Sum(md5.Sum(decoded)) == entry.checksum
	stage := "decoded_payload"
	if storedMatch && payloadMatch {
		stage = "both"
	} else if storedMatch {
		stage = "decrypted_stored"
	} else if !payloadMatch {
		return nil, "", fail("container_checksum_mismatch")
	}
	return decoded, stage, nil
}

// Exported fields below are metadata only; no archive entry/key/body is marshaled.
type member struct {
	Name                string
	NameOmitted         bool
	Offset, Size        uint32
	AllocationCandidate bool
	StoredSHA256        string
}
type packMetadata struct {
	Kind, SHA256 string
	Members      []member
	References   []string
	Omitted      int
}

func assetName(data []byte, offset, length uint32, tableEnd uint64) (string, bool, error) {
	if length == 0 || length > maxNameBytes || uint64(offset) < tableEnd ||
		!span(uint64(offset), uint64(length), uint64(len(data))) {
		return "", false, fail("fpk_name_limit_or_bounds")
	}
	raw := data[uint64(offset) : uint64(offset)+uint64(length)]
	name := string(raw)
	allowed := utf8.Valid(raw) && strings.HasPrefix(name, "/Assets/") && path.Clean(name) == name
	for _, char := range raw {
		if !((char >= 'A' && char <= 'Z') || (char >= 'a' && char <= 'z') ||
			(char >= '0' && char <= '9') || strings.ContainsRune("_./-", rune(char))) {
			allowed = false
		}
	}
	if !allowed {
		return "<name omitted>", true, nil
	}
	return name, false, nil
}

func isAllocationCandidate(name string) bool {
	return strings.HasPrefix(name, "/Assets/tpp/level_asset/chara/player/game_object/") &&
		(strings.Contains(path.Base(name), "instance") || strings.Contains(path.Base(name), "parts"))
}

// Read tables and names; never call Fpk.Read/Entry.ReadData or emit member bodies.
func inspectFPK(data []byte) (packMetadata, error) {
	out := packMetadata{Members: []member{}, References: []string{}}
	if len(data) < fpk.HeaderSize || len(data) > maxPackBytes {
		return out, fail("fpk_header_or_size_limit")
	}
	header := fpk.Header{}
	if err := header.Read(bytes.NewReader(data[:fpk.HeaderSize])); err != nil {
		return out, fail("fpk_magic")
	}
	tableEnd := uint64(fpk.HeaderSize) + uint64(header.EntryCount)*48 + uint64(header.RefCount)*16
	if header.MagicNumber2 != 2 || uint64(header.EntryCount)+uint64(header.RefCount) > maxNames {
		return out, fail("fpk_version_or_count_limit")
	}
	if uint64(header.FileSize) != uint64(len(data)) || tableEnd > uint64(len(data)) {
		return out, fail("fpk_table_or_declared_size")
	}
	out.Kind = "fpk"
	if header.IsFpkd() {
		out.Kind = "fpkd"
	}
	digest := sha256.Sum256(data)
	out.SHA256 = hex.EncodeToString(digest[:])
	for i := uint32(0); i < header.EntryCount; i++ {
		position := uint64(fpk.HeaderSize) + uint64(i)*48
		row := data[position : position+48]
		offset, size := le.Uint32(row), le.Uint32(row[8:])
		if uint64(offset) < tableEnd || !span(uint64(offset), uint64(size), uint64(len(data))) {
			return out, fail("fpk_member_bounds")
		}
		name, omitted, err := assetName(data, le.Uint32(row[16:]), le.Uint32(row[24:]), tableEnd)
		if err != nil {
			return out, err
		}
		item := member{Name: name, NameOmitted: omitted, Offset: offset, Size: size,
			AllocationCandidate: !omitted && isAllocationCandidate(name)}
		if item.AllocationCandidate {
			sum := sha256.Sum256(data[uint64(offset) : uint64(offset)+uint64(size)])
			item.StoredSHA256 = hex.EncodeToString(sum[:])
		}
		out.Members = append(out.Members, item)
		if omitted {
			out.Omitted++
		}
	}
	for i := uint32(0); i < header.RefCount; i++ {
		position := uint64(fpk.HeaderSize) + uint64(header.EntryCount)*48 + uint64(i)*16
		row := data[position : position+16]
		name, omitted, err := assetName(data, le.Uint32(row), le.Uint32(row[8:]), tableEnd)
		if err != nil {
			return out, err
		}
		out.References = append(out.References, name)
		if omitted {
			out.Omitted++
		}
	}
	return out, nil
}
