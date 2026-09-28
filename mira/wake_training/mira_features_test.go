package oww

import (
 "encoding/binary"
 "os"
 "path/filepath"
 "testing"
)

// Export the exact Echo front end, not a different training implementation.
func TestMiraFeatures(t *testing.T) {
 dir := os.Getenv("MIRA_CLIPS")
 if dir == "" { t.Skip("MIRA_CLIPS required") }
 clips, err := filepath.Glob(filepath.Join(dir, "*.wav"))
 if err != nil { t.Fatal(err) }
 for _, clip := range clips {
  pcm := readWAV(t, clip)
  e, err := New(); if err != nil { t.Fatal(err) }
  e.maxFrames = 1 << 20
  pad := make([]int16, SampleRate)
  pcm = append(append(append([]int16{}, pad...), pcm...), pad...)
  for off := 0; off < len(pcm); off += 320 {
   if _, err := e.Process(pcm[off:min(off+320,len(pcm))]); err != nil {t.Fatal(err)}
  }
  out, err := os.Create(clip+".features"); if err != nil {t.Fatal(err)}
  if err := binary.Write(out,binary.LittleEndian,e.feats); err != nil {t.Fatal(err)}
  out.Close()
 }
 t.Logf("exported %d clips",len(clips))
}
