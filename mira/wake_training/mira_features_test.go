package oww

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"testing"
)

// Export the exact Echo front end, not a different training implementation.
//
// Copy this file into TECHO5's echod/internal/lib/oww (setup.sh stages a copy of that package
// under the cache directory, so the TECHO5 checkout is never modified) and run one of:
//
//	MIRA_CLIPS=<dir>    go test -run TestMiraFeatures   every <dir>/*.wav -> <wav>.features
//	MIRA_BATCH=<prefix> go test -run TestMiraFeatures   <prefix>.pcm + .idx -> <prefix>.feats + .fidx
//	MIRA_SCORE_MODEL=<m.tflite> MIRA_BATCH=<prefix> go test -run TestMiraScore
//	                                                    -> <prefix>.scores + .sidx
//
// Each clip gets a fresh engine, MIRA_PAD samples of digital silence on both sides (default 16000,
// one second, as the first exporter) and is fed in 320-sample (20 ms) frames, the size echod's
// microphone loop hands the detector. A .features/.feats record is every embedding the engine
// produced, float32 little endian, 96 per 80 ms step. MIRA_WORKERS (default: every CPU) clips run in
// parallel; each owns its engine, so the numbers do not depend on the worker count.
//
// Batch files: <prefix>.pcm is int16 LE mono 16 kHz, all clips concatenated, and <prefix>.idx one
// "offset length" pair per line, in samples. Outputs keep the input order: .feats is the embeddings
// concatenated and .fidx one embedding count per line. TestMiraScore loads the classifier into the
// engine echod runs (Engine.Load + Process) and writes every score Process returned, float32 LE,
// with one score count per clip in .sidx.
func TestMiraFeatures(t *testing.T) {
	dir, batch := os.Getenv("MIRA_CLIPS"), os.Getenv("MIRA_BATCH")
	if dir == "" && batch == "" {
		t.Skip("MIRA_CLIPS or MIRA_BATCH required")
	}
	pad := envCount(t, "MIRA_PAD", SampleRate)
	workers := envCount(t, "MIRA_WORKERS", runtime.NumCPU())

	if dir != "" {
		clips, err := filepath.Glob(filepath.Join(dir, "*.wav"))
		if err != nil {
			t.Fatal(err)
		}
		pcms := make([][]int16, len(clips))
		for i, clip := range clips {
			pcms[i] = readWAV(t, clip)
		}
		feats := runAll(t, pcms, pad, workers, miraFeatures)
		for i, clip := range clips {
			out, err := os.Create(clip + ".features")
			if err != nil {
				t.Fatal(err)
			}
			if err := binary.Write(out, binary.LittleEndian, feats[i]); err != nil {
				t.Fatal(err)
			}
			if err := out.Close(); err != nil {
				t.Fatal(err)
			}
		}
		t.Logf("exported %d clips", len(clips))
		return
	}

	pcms := readBatch(t, batch)
	feats := runAll(t, pcms, pad, workers, miraFeatures)
	writeBatch(t, batch+".feats", batch+".fidx", feats, EmbeddingDims)
	t.Logf("exported %d clips from %s", len(pcms), batch)
}

// TestMiraScore scores a batch with a classifier through the engine echod runs, so a training
// pipeline can prove that its own scoring of the embeddings equals the device's.
func TestMiraScore(t *testing.T) {
	model, batch := os.Getenv("MIRA_SCORE_MODEL"), os.Getenv("MIRA_BATCH")
	if model == "" || batch == "" {
		t.Skip("MIRA_SCORE_MODEL and MIRA_BATCH required")
	}
	raw, err := os.ReadFile(model)
	if err != nil {
		t.Fatal(err)
	}
	pad := envCount(t, "MIRA_PAD", SampleRate)
	workers := envCount(t, "MIRA_WORKERS", runtime.NumCPU())
	pcms := readBatch(t, batch)
	scores := runAll(t, pcms, pad, workers, func(pcm []int16) ([]float32, error) {
		e, err := New()
		if err != nil {
			return nil, err
		}
		if _, err := e.Load("m", raw); err != nil {
			return nil, err
		}
		var seq []float32
		for off := 0; off < len(pcm); off += 320 {
			s, err := e.Process(pcm[off:min(off+320, len(pcm))])
			if err != nil {
				return nil, err
			}
			// A 320-sample frame completes at most one 1280-sample step: at most one new score.
			if v, ok := s["m"]; ok {
				seq = append(seq, v)
			}
		}
		return seq, nil
	})
	writeBatch(t, batch+".scores", batch+".sidx", scores, 1)
	t.Logf("scored %d clips from %s with %s", len(pcms), batch, model)
}

// miraFeatures is the first exporter's loop for one clip, already padded.
func miraFeatures(pcm []int16) ([]float32, error) {
	e, err := New()
	if err != nil {
		return nil, err
	}
	e.maxFrames = 1 << 20
	for off := 0; off < len(pcm); off += 320 {
		if _, err := e.Process(pcm[off:min(off+320, len(pcm))]); err != nil {
			return nil, err
		}
	}
	return e.feats, nil
}

func runAll(t *testing.T, pcms [][]int16, pad, workers int, one func([]int16) ([]float32, error)) [][]float32 {
	t.Helper()
	out := make([][]float32, len(pcms))
	errs := make([]error, len(pcms))
	jobs := make(chan int)
	var wg sync.WaitGroup
	for range max(1, workers) {
		wg.Add(1)
		go func() {
			defer wg.Done()
			silence := make([]int16, pad)
			for i := range jobs {
				pcm := append(append(append([]int16{}, silence...), pcms[i]...), silence...)
				out[i], errs[i] = one(pcm)
			}
		}()
	}
	for i := range pcms {
		jobs <- i
	}
	close(jobs)
	wg.Wait()
	for i, err := range errs {
		if err != nil {
			t.Fatalf("clip %d: %v", i, err)
		}
	}
	return out
}

func readBatch(t *testing.T, prefix string) [][]int16 {
	t.Helper()
	raw, err := os.ReadFile(prefix + ".pcm")
	if err != nil {
		t.Fatal(err)
	}
	idx, err := os.Open(prefix + ".idx")
	if err != nil {
		t.Fatal(err)
	}
	defer idx.Close()
	var pcms [][]int16
	sc := bufio.NewScanner(idx)
	for sc.Scan() {
		f := strings.Fields(sc.Text())
		if len(f) == 0 {
			continue
		}
		if len(f) != 2 {
			t.Fatalf("%s.idx: %q is not \"offset length\"", prefix, sc.Text())
		}
		off, err1 := strconv.Atoi(f[0])
		n, err2 := strconv.Atoi(f[1])
		if err1 != nil || err2 != nil || off < 0 || n < 0 || 2*(off+n) > len(raw) {
			t.Fatalf("%s.idx: bad record %q", prefix, sc.Text())
		}
		pcm := make([]int16, n)
		for i := range pcm {
			pcm[i] = int16(binary.LittleEndian.Uint16(raw[2*(off+i):]))
		}
		pcms = append(pcms, pcm)
	}
	if err := sc.Err(); err != nil {
		t.Fatal(err)
	}
	return pcms
}

func writeBatch(t *testing.T, dataPath, idxPath string, rows [][]float32, width int) {
	t.Helper()
	data, err := os.Create(dataPath + ".tmp")
	if err != nil {
		t.Fatal(err)
	}
	w := bufio.NewWriterSize(data, 1<<20)
	var counts strings.Builder
	for _, r := range rows {
		if err := binary.Write(w, binary.LittleEndian, r); err != nil {
			t.Fatal(err)
		}
		fmt.Fprintf(&counts, "%d\n", len(r)/width)
	}
	if err := w.Flush(); err != nil {
		t.Fatal(err)
	}
	if err := data.Close(); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(idxPath+".tmp", []byte(counts.String()), 0o644); err != nil {
		t.Fatal(err)
	}
	// The index last: whoever finds the index finds complete data beside it.
	for _, p := range []string{dataPath, idxPath} {
		if err := os.Rename(p+".tmp", p); err != nil {
			t.Fatal(err)
		}
	}
}

func envCount(t *testing.T, name string, def int) int {
	t.Helper()
	v := os.Getenv(name)
	if v == "" {
		return def
	}
	n, err := strconv.Atoi(v)
	if err != nil || n < 0 {
		t.Fatalf("%s=%q is not a count", name, v)
	}
	return n
}
