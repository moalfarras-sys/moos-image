import type { RemoteModel } from "./model";
import { SheetPanel, Tabs } from "../kit";
import {
  IconArrowUp, IconClipboard, IconCopy, IconFile, IconFolder, IconImage, IconPaste, IconRefresh, IconSend,
  IconTransfer, IconUpload,
} from "../icons";

/**
 * Moving things between this device and the computer, in one place.
 *
 * Clipboard: the two everyday actions first (copy what is selected on the PC to this device; paste
 * this device's clipboard into the PC), then the explicit, inspectable versions of both directions
 * for text and images. Nothing is synchronised in the background, and a failed transfer never
 * presses Paste on the PC (it would paste whatever was there before).
 *
 * Files: browse the PC's home, download a file, upload into the open folder (resumable).
 */
export function TransferSheet({ m }: { m: RemoteModel }) {
  const { tr } = m;
  return (
    <SheetPanel label={tr("transferTitle")} closeLabel={`${tr("closePrefix")} ${tr("transferTitle")}`}
                onClose={m.closeSheet} title={tr("transferTitle")} icon={<IconTransfer />} className="transfer-sheet">
      <Tabs idPrefix="transfer" label={tr("transferTitle")} value={m.transferTab} onChange={m.setTransferTab}
            tabs={[
              { value: "clipboard", label: tr("clipboard"), icon: <IconClipboard /> },
              { value: "files", label: tr("filesTitle"), icon: <IconFolder /> },
            ]} />
      <div id="transfer-panel" role="tabpanel" aria-labelledby={`transfer-tab-${m.transferTab}`} className="tab-panel">
        {m.transferTab === "clipboard" ? <ClipboardTab m={m} /> : <FilesTab m={m} />}
      </div>
    </SheetPanel>
  );
}

function ClipboardTab({ m }: { m: RemoteModel }) {
  const { tr, pcClip, sendText, clipboardBusy } = m;
  return (
    <>
      <div className="hero-actions">
        <button type="button" className="hero-btn" onClick={() => void m.copyFromPc()}>
          <IconCopy /><span>{tr("copyToThisDevice")}</span>
        </button>
        <button type="button" className="hero-btn" onClick={() => void m.pasteFromDevice()}>
          <IconPaste /><span>{tr("pasteFromThisDevice")}</span>
        </button>
      </div>
      {!m.clipboardOk && <p className="hint warn" role="status">{tr("clipboardNotReady")}</p>}

      <section className="section">
        <div className="section-head"><h4>{tr("pcToPhone")}</h4></div>
        <div className="card card-pad stack">
          {pcClip.kind === "image" ? (
            <img className="clip-img" src={pcClip.dataUrl} alt={tr("pcToPhone")} />
          ) : (
            <textarea className="clip-area" dir="auto" aria-label={tr("pcToPhone")} readOnly value={pcClip.text ?? ""}
                      placeholder={tr("pressGetToFetch")} />
          )}
          <div className="button-pair">
            <button type="button" className="chip" onClick={() => void m.getPcClip()}><IconRefresh /> {tr("getPcClipboard")}</button>
            <button type="button" className="chip" onClick={() => void m.copyToPhone()} disabled={pcClip.kind !== "text"}>
              <IconCopy /> {tr("copy")}</button>
          </div>
          {pcClip.kind === "image" && <div className="hint">{tr("longPressImageSaveCopy")}</div>}
        </div>
      </section>

      <section className="section">
        <div className="section-head"><h4>{tr("phoneToPcText")}</h4></div>
        <div className="card card-pad stack">
          <button type="button" className="chip wide" onClick={() => void m.readPhoneClip()}><IconPaste />{tr("readPhoneClipboard")}</button>
          <textarea ref={m.phoneClipRef} className="clip-area" dir="auto" aria-label={tr("phoneToPcText")} value={sendText}
                    onChange={(e) => m.setSendText(e.target.value)} placeholder={tr("typeOrPasteText")} />
          <div className="button-pair">
            <button type="button" className="chip" disabled={!sendText || !!clipboardBusy} onClick={() => void m.sendToPc(false)}>
              <IconClipboard /> {tr("setOnly")}
            </button>
            <button type="button" className="chip primary" disabled={!sendText || !!clipboardBusy} onClick={() => void m.sendToPc(true)}>
              <IconSend /> {tr("sendPaste")}
            </button>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-head"><h4>{tr("phoneToPcImage")}</h4></div>
        <div className="card card-pad">
          <div className="button-pair">
            <button type="button" className="chip" disabled={!!clipboardBusy} onClick={() => m.pickImage(false)}>
              <IconImage /> {tr("setImageOnly")}
            </button>
            <button type="button" className="chip primary" disabled={!!clipboardBusy} onClick={() => m.pickImage(true)}>
              <IconSend /> {tr("photoAndPaste")}
            </button>
          </div>
        </div>
      </section>
      {clipboardBusy && <div className="transfer-status" role="status" aria-live="polite"><i />{clipboardBusy}</div>}
      <div
        className="paste-box"
        contentEditable
        suppressContentEditableWarning
        onPaste={(e) => void m.onPasteBox(e)}
        onInput={m.onPasteBoxInput}
        data-ph={tr("longPressPasteHint")}
      />
    </>
  );
}

function FilesTab({ m }: { m: RemoteModel }) {
  const { tr, fileList, fileBusy } = m;
  return (
    <>
      <div className="files-head">
        <b dir="auto">{fileList?.title ?? "…"}</b>
        <div className="button-pair">
          {fileList?.path && <button type="button" className="chip" onClick={() => void m.navFiles(fileList.parent)}><IconArrowUp /> {tr("up")}</button>}
          {fileList?.path && <button type="button" className="chip primary" onClick={m.pickUpload}><IconUpload /> {tr("uploadHere")}</button>}
          <button type="button" className="chip" onClick={() => void m.navFiles(fileList?.path ?? null)}
                  aria-label={tr("refresh")}><IconRefresh /></button>
        </div>
      </div>
      <div className="file-list card">
        {fileBusy && <div className="hintline" role="status">{m.uploadProgress || tr("loadingEllipsis")}</div>}
        {!fileBusy && fileList?.truncated &&
          <div className="hintline" role="status">{tr("truncatedFolderNotice")}</div>}
        {!fileBusy && fileList && fileList.entries.length === 0 && <div className="hintline">{tr("emptyFolder")}</div>}
        {!fileBusy && fileList?.entries.map((en) => (
          <button type="button" key={en.path} className="file-row"
                  onClick={() => void (en.isDir ? m.navFiles(en.path) : m.downloadFile(en))}>
            <span className="file-ic">{en.isDir ? <IconFolder /> : <IconFile />}</span>
            <span className="file-name" dir="auto">{en.name}</span>
            <span className="file-meta">{en.isDir ? (m.lang === "ar" ? "‹" : "›") : m.fmtSize(en.size)}</span>
          </button>
        ))}
      </div>
    </>
  );
}
