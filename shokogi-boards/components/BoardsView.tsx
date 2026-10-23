"use client";

// Boards page (SPEC 7.6): photo-folder import, add a single board, search + filter, cards grouped by type.
import { useState } from "react";
import { boardNameFromFile, byName, detectType, isImage, matcher, uniqueName } from "@/lib/boards";
import { copies, type Board, type Fleet } from "@/lib/data";
import { photoUrl, setBoardPhoto } from "@/lib/photos";
import { createClient } from "@/lib/supabase/client";
import { plural } from "@/lib/time";
import { useApp } from "./app";
import { BoardStatus, inState, RepairButtons, shownTypes, useBoardActions, type BoardState } from "./boards";
import { Icon } from "./icons";

const INTRO = "Import a photo folder: each file name becomes the board name, and its first word sets the type (for example FUNBOARD or SHORTBOARD; types are managed in Settings). JPG, PNG and iPhone HEIC are supported.";
const FILTERS: [BoardState | "all", string][] = [["all", "All"], ["free", "Available"], ["out", "Rented"], ["fix", "In repair"]];

function BoardCard({ fleet, board }: { fleet: Fleet; board: Board }) {
  const { me, openBoard } = useApp();
  const actions = useBoardActions();
  const { out } = copies(fleet.rentedBy, board);
  const times = fleet.stats.get(board.id)?.times_rented;
  return (
    <div className="board">
      <button className="photo" title="Board details" onClick={() => openBoard(board.id)}>
        {board.thumb_path ? <img src={photoUrl(board.thumb_path)} alt="" loading="lazy" /> : "No photo"}
      </button>
      <div className="body">
        <div className="name">{board.name}{board.quantity > 1 && <span className="muted qty"> ×{board.quantity}</span>}</div>
        <div className="row"><BoardStatus fleet={fleet} board={board} withName /><span className="muted">{times ? `Rented ${plural(times, "time")}` : ""}</span></div>
        <div className="foot">
          <select title="Board type" value={board.type_id} onChange={(e) => actions.update(board, { type_id: e.target.value })}>
            {fleet.types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <RepairButtons fleet={fleet} board={board} small />
          {!out && me.role === "owner" && <button className="btn sm danger" onClick={() => actions.remove(board)}>Delete</button>}
        </div>
      </div>
    </div>
  );
}

export default function BoardsView() {
  const db = createClient();
  const { fleet, refresh, toast } = useApp();
  const [status, setStatus] = useState(INTRO);
  const [importing, setImporting] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<BoardState | "all">("all");
  const [photoName, setPhotoName] = useState("");
  if (!fleet) return <section><div className="top"><div><h1>Boards</h1></div></div><p className="empty">Loading…</p></section>;

  const other = fleet.types.find((t) => t.is_system)!;

  // Re-importing a file with the same original name updates that board's photo instead of adding a board.
  // One photo at a time: decoding several iPhone photos at once can run a phone out of memory.
  async function importFolder(list: FileList | null) {
    const files = [...(list ?? [])].filter(isImage);
    if (!files.length) return setStatus("No photos in that folder. JPG, PNG and iPhone HEIC are supported.");
    setImporting(true);
    const typeNames = fleet!.types.filter((t) => !t.is_system).map((t) => t.name);
    const typeId = (name: string) => fleet!.types.find((t) => t.name === name)?.id ?? other.id;
    const bySource = new Map(fleet!.boards.filter((b) => b.source_file_name).map((b) => [b.source_file_name!, b]));
    const taken = new Set(fleet!.boards.map((b) => b.name));
    let added = 0, updated = 0;
    const failed: string[] = [];
    for (const [i, file] of files.entries()) {
      setStatus(`Importing ${i + 1} of ${files.length}…`);
      try {
        let board = bySource.get(file.name);
        if (board) updated++;
        else {
          const base = boardNameFromFile(file.name);
          const name = uniqueName(base, taken);
          taken.add(name);
          const { data } = await db.from("boards")
            .insert({ name, type_id: typeId(detectType(base, file.webkitRelativePath, typeNames)), source_file_name: file.name })
            .select().single().throwOnError();
          board = data as Board;
          bySource.set(file.name, board);
          added++;
        }
        await setBoardPhoto(db, board, file);
      } catch {
        failed.push(file.name);
      }
      if (i % 10 === 9) refresh(); // let the new boards show up while the rest imports
    }
    await refresh();
    setImporting(false);
    setStatus(`Done: ${plural(added, "new board")}, ${updated} updated.` + (failed.length ? ` Couldn't read: ${failed.join(", ")}` : ""));
  }

  async function addBoard(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget, f = new FormData(form);
    const name = String(f.get("name")).trim(), photo = f.get("photo") as File | null;
    if (!name) return;
    try {
      const { data } = await db.from("boards").insert({ name, type_id: String(f.get("type")), quantity: Number(f.get("quantity")) || 1 })
        .select().single().throwOnError();
      (form.elements.namedItem("name") as HTMLInputElement).value = ""; // keep the type for the next board
      (form.elements.namedItem("quantity") as HTMLInputElement).value = "1";
      (form.elements.namedItem("photo") as HTMLInputElement).value = "";
      setPhotoName("");
      if (photo?.size) await setBoardPhoto(db, data as Board, photo);
    } catch {
      toast("Couldn't add the board. Check the connection and try again.", "error");
    }
    await refresh();
  }

  const has = matcher(query);
  const shown = fleet.boards.filter((b) => has(b.name) && (filter === "all" || inState(fleet, b, filter) > 0)).sort(byName);
  const total = (f: BoardState | "all") => fleet.boards.reduce((n, b) => n + (f === "all" ? b.quantity : inState(fleet, b, f)), 0); // copies
  const groups = shownTypes(fleet).map((t) => ({ type: t, boards: shown.filter((b) => b.type_id === t.id) })).filter((g) => g.boards.length);

  return (
    <section>
      <div className="top">
        <div><h1>Boards</h1><p className="sub" role="status">{status}</p></div>
        <label className="btn primary" aria-disabled={importing}>
          <Icon name="upload" />Import photo folder
          <input type="file" multiple hidden disabled={importing} {...{ webkitdirectory: "" }}
            onChange={(e) => { importFolder(e.target.files); e.target.value = ""; }} />
        </label>
      </div>
      <details className="panel">
        <summary><Icon name="plus" />Add a single board</summary>
        <form className="form" onSubmit={addBoard}>
          <select name="type" defaultValue={fleet.types[0]?.id}>{fleet.types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
          <input name="name" placeholder="Board name, e.g. FUNBOARD 7'0 TORQ" required />
          <label className="qty-field" title="How many identical boards you have">Quantity
            <input name="quantity" type="number" min={1} max={999} defaultValue={1} required />
          </label>
          <label className="btn">
            <input type="file" name="photo" accept="image/*,.heic,.heif" hidden onChange={(e) => setPhotoName(e.target.files?.[0]?.name ?? "")} />
            <span>{photoName || "Choose photo"}</span>
          </label>
          <button className="btn primary">Add board</button>
        </form>
      </details>
      <div className="toolbar">
        <input type="search" placeholder="Search boards, e.g. torq 7'6" value={query} onChange={(e) => setQuery(e.target.value)} />
        <div className="seg">
          {FILTERS.map(([f, label]) => (
            <button key={f} className={f === filter ? "on" : undefined} onClick={() => setFilter(f)}>
              {label}<span>{total(f)}</span>
            </button>
          ))}
        </div>
      </div>
      {groups.length ? groups.map(({ type, boards }) => (
        <div key={type.id}>
          <div className="group"><h2>{type.name}</h2><span className="muted">{plural(boards.length, "board")}</span></div>
          <div className="grid">{boards.map((b) => <BoardCard key={b.id} fleet={fleet} board={b} />)}</div>
        </div>
      )) : <p className="empty">{fleet.boards.length ? "No boards match." : "No boards yet. Import your photo folder to start."}</p>}
    </section>
  );
}
