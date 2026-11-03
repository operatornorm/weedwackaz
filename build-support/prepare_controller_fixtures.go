// Cloud-only trusted fixture preparation; never reads an owner's install or saves.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"strings"

	"github.com/unknown321/datfpk/fox2"
	"github.com/unknown321/datfpk/fox2/containers"
	"github.com/unknown321/datfpk/fox2/datatypes/fox"
	"github.com/unknown321/datfpk/fpk"
	"github.com/unknown321/datfpk/util"
	"github.com/unknown321/hashing"
)

func must(err error) {
	if err != nil {
		panic(err)
	}
}

func main() {
	if len(os.Args) != 4 {
		panic("args: patched dynamite source, pinned module cache, ignored fixture output")
	}
	if os.Args[1] == "--verify-transform" {
		oldData, err := os.ReadFile(os.Args[2])
		must(err)
		newData, err := os.ReadFile(os.Args[3])
		must(err)
		oldPack, newPack := fpk.Fpk{}, fpk.Fpk{}
		must(oldPack.Read(bytes.NewReader(oldData), false))
		must(newPack.Read(bytes.NewReader(newData), false))
		if len(oldPack.Entries) != 3 || len(newPack.Entries) != 2 || len(oldPack.References) != len(newPack.References) {
			panic("wrong output cardinality")
		}
		oldKept := []fpk.Entry{}
		for _, entry := range oldPack.Entries {
			if strings.HasSuffix(entry.FilePath.Data, "/single_player2_instance.fox2") {
				continue
			}
			oldKept = append(oldKept, entry)
		}
		for i, entry := range newPack.Entries {
			if entry.FilePath.Data != oldKept[i].FilePath.Data || !bytes.Equal(entry.Data, oldKept[i].Data) || entry.PathMD5 != oldKept[i].PathMD5 {
				panic("SDK preservation mismatch")
			}
		}
		for i, ref := range newPack.References {
			if ref.FilePath.Data != oldPack.References[i].FilePath.Data {
				panic("SDK reference mismatch")
			}
		}
		fmt.Println("PASS: independent pinned FPK reader accepts transformed synthetic package and unchanged members/references")
		return
	}
	if os.Args[1] == "--verify-expanded" {
		before, err := os.ReadFile(os.Args[2])
		must(err)
		after, err := os.ReadFile(os.Args[3])
		must(err)
		oldPack, newPack := fpk.Fpk{}, fpk.Fpk{}
		must(oldPack.Read(bytes.NewReader(before), false))
		must(newPack.Read(bytes.NewReader(after), false))
		if len(oldPack.Entries) != len(newPack.Entries) || !reflect.DeepEqual(oldPack.References, newPack.References) {
			panic("expanded package shape changed")
		}
		checked := 0
		for i, oldEntry := range oldPack.Entries {
			newEntry := newPack.Entries[i]
			if oldEntry.FilePath.Data != newEntry.FilePath.Data || oldEntry.PathMD5 != newEntry.PathMD5 {
				panic("expanded names/MD5 changed")
			}
			if !strings.Contains(oldEntry.FilePath.Data, "single_player2_instance") && !strings.Contains(oldEntry.FilePath.Data, "single_pl2_instance_scarf") {
				if !bytes.Equal(oldEntry.Data, newEntry.Data) {
					panic("expanded unrelated payload changed")
				}
				continue
			}
			oldFox, newFox := fox2.Fox2{}, fox2.Fox2{}
			must(oldFox.Read(bytes.NewReader(oldEntry.Data)))
			must(newFox.Read(bytes.NewReader(newEntry.Data)))
			if len(oldFox.Entities) != len(newFox.Entities) || oldFox.Header.StringTableOffset != newFox.Header.StringTableOffset {
				panic("expanded FOX2 layout changed")
			}
			for j, oldEntity := range oldFox.Entities {
				newEntity := newFox.Entities[j]
				if !reflect.DeepEqual(oldEntity.Header, newEntity.Header) {
					panic("expanded entity header changed")
				}
				if oldEntity.ClassNameString != "TppPlayer2BlockControllerData" {
					if !reflect.DeepEqual(oldEntity, newEntity) {
						panic("expanded unrelated entity changed")
					}
					continue
				}
				if len(oldEntity.StaticProperties) != len(newEntity.StaticProperties) {
					panic("expanded property count changed")
				}
				for k, oldProp := range oldEntity.StaticProperties {
					newProp := newEntity.StaticProperties[k]
					switch oldProp.NameValue {
					case "configuration_partsBlockCount":
						if newProp.Value.(*containers.FoxStaticArray).Data[0].(*fox.UInt32).Value != 2 {
							panic("expanded parts count")
						}
					case "instanceSettings_instanceBlockSize":
						if newProp.Value.(*containers.FoxStaticArray).Data[0].(*fox.UInt32).Value != 1126400 {
							panic("expanded instance block")
						}
					case "instanceSettings_instancePackagePath":
						if newProp.Value.(*containers.FoxStaticArray).Data[0].(*fox.String).Value != "/Assets/tpp/pack/player/game_object/two_players_game_obj.fpk" {
							panic("expanded instance path")
						}
					case "instanceSettings_partsTypeNames", "instanceSettings_partsTypeInitial":
						oldValues := oldProp.Value.(*containers.FoxDynamicArray).Data
						newValues := newProp.Value.(*containers.FoxDynamicArray).Data
						if len(oldValues) != 1 || len(newValues) != 2 || !reflect.DeepEqual(oldValues[0], newValues[0]) || !reflect.DeepEqual(oldValues[0], newValues[1]) {
							panic("expanded profile changed")
						}
					default:
						if !reflect.DeepEqual(oldProp, newProp) {
							panic("expanded unrelated property changed")
						}
					}
				}
			}
			checked++
		}
		if checked != 1 {
			panic("expanded target not unique")
		}
		fmt.Println("PASS: pinned native readers verify expanded profile, five changed fields and unchanged entities/members")
		return
	}
	source, cache, output := os.Args[1], os.Args[2], os.Args[3]
	must(os.MkdirAll(output, 0700))
	base := filepath.Join(cache, "github.com/unknown321/datfpk@v0.3.0/fox2/testdata")
	checks := []map[string]any{}
	for _, name := range []string{"bool", "uint32", "string", "path", "entityptr", "entityhandle", "fileptr", "int32", "uint64"} {
		path := filepath.Join(base, "types", name+".foxtool.fox2")
		data, err := os.ReadFile(path)
		must(err)
		f := fox2.Fox2{}
		must(f.Read(bytes.NewReader(data)))
		check := map[string]any{"file": name + ".fox2", "entities": []map[string]any{}}
		entities := []map[string]any{}
		for _, e := range f.Entities {
			properties := []map[string]any{}
			for _, p := range append(e.StaticProperties, e.DynamicProperties...) {
				properties = append(properties, map[string]any{"hash": p.Header.NameHash, "type": p.Header.DataType,
					"container": p.Header.ContainerType, "count": p.Header.ValueCount})
			}
			entities = append(entities, map[string]any{"class_hash": e.Header.ClassNameHash, "properties": properties})
		}
		check["entities"] = entities
		checks = append(checks, check)
		must(os.WriteFile(filepath.Join(output, name+".fox2"), data, 0600))
	}
	// Independently supplied game fixture, separate from our modified source XML.
	data, err := os.ReadFile(filepath.Join(base, "game/player2_add_parts_prqst_x1.fox2"))
	must(err)
	must(os.WriteFile(filepath.Join(output, "additional_parts.fox2"), data, 0600))
	modelDir := filepath.Join(source, "moddata/coop_essentials/coop_essentials_fpkd/Assets/tpp/level_asset/chara/player/game_object")
	for _, name := range []string{"two_player2_instances", "player2_additional_parts_x1", "player2_online_motion", "player2_mtbs_motion_loader"} {
		xml, err := os.ReadFile(filepath.Join(modelDir, name+".fox2.xml"))
		must(err)
		f := fox2.Fox2{}
		must(f.FromXML(bytes.NewReader(xml)))
		buf := util.NewByteArrayReaderWriter(nil)
		must(f.Write(buf))
		must(os.WriteFile(filepath.Join(output, name+".fox2"), buf.Bytes(), 0600))
		if name != "two_player2_instances" {
			continue
		}
		for i := range f.Entities {
			if f.Entities[i].ClassNameString != "TppPlayer2BlockControllerData" {
				continue
			}
			for j := range f.Entities[i].StaticProperties {
				p := &f.Entities[i].StaticProperties[j]
				switch p.NameValue {
				case "configuration_partsBlockCount":
					p.Value.(*containers.FoxStaticArray).Data[0].(*fox.UInt32).Value = 1
				case "instanceSettings_partsTypeNames", "instanceSettings_partsTypeInitial":
					p.Header.ValueCount = 1
					p.Value.(*containers.FoxDynamicArray).Data = p.Value.(*containers.FoxDynamicArray).Data[:1]
				case "instanceSettings_instancePackagePath":
					p.Value.(*containers.FoxStaticArray).Data[0].(*fox.String).Value = "/Assets/tpp/pack/player/game_object/synthetic_single.fpk"
				}
			}
		}
		buf = util.NewByteArrayReaderWriter(nil)
		must(f.Write(buf))
		must(os.WriteFile(filepath.Join(output, "synthetic_single.fox2"), buf.Bytes(), 0600))
		// Structurally match captured scalar values, without using owner body bytes.
		for _, profile := range []string{"Normal", "NormalScarf"} {
			for i := range f.Entities {
				if f.Entities[i].ClassNameString != "TppPlayer2BlockControllerData" {
					continue
				}
				for j := range f.Entities[i].StaticProperties {
					p := &f.Entities[i].StaticProperties[j]
					switch p.NameValue {
					case "instanceSettings_instanceBlockSize":
						p.Value.(*containers.FoxStaticArray).Data[0].(*fox.UInt32).Value = 563200
					case "instanceSettings_instancePackagePath":
						p.Value.(*containers.FoxStaticArray).Data[0].(*fox.String).Value = "/Assets/tpp/pack/player/game_object/single_player_game_obj.fpk"
					case "instanceSettings_partsTypeNames", "instanceSettings_partsTypeInitial":
						p.Value.(*containers.FoxDynamicArray).Data[0].(*fox.String).Value = "PLType" + profile
					}
				}
			}
			buf = util.NewByteArrayReaderWriter(nil)
			must(f.Write(buf))
			must(os.WriteFile(filepath.Join(output, "synthetic_profile_"+profile+".fox2"), buf.Bytes(), 0600))
		}
	}
	vectors := map[string]string{}
	for _, s := range []string{"", "name", "DataSet", "dataSet", "dataList", "TppPlayer2BlockControllerData",
		"configuration_partsBlockCount", "instanceSettings_partsTypeInitial", strings.Repeat("x", 127)} {
		vectors[s] = fmt.Sprintf("%012x", hashing.StrCode64([]byte(s)))
	}
	encoded, err := json.MarshalIndent(map[string]any{"fixtures": checks, "hash_vectors": vectors}, "", "  ")
	must(err)
	must(os.WriteFile(filepath.Join(output, "reference.json"), encoded, 0600))
	fmt.Println("Prepared pinned external FOX2 fixtures and explicitly synthetic single-slot reference")
}
