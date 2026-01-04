#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quiet_map_app.py

Lane-based discussion map (賛成/反対/非賛否) with a built-in sample:
きのこ派 vs たけのこ派論争（少し充実版）

Features
- 左から「賛成列 → 反対列 → 賛成列…」のレーン表示
- 非賛否（meta）レーン（前提・定義・問い・補足・論点ずらし等）を別領域に配置
- ノード右クリック：追加（接続詞ベース）/削除
- ノードダブルクリック：簡易編集（接続詞＋本文）
- JSON保存/読込
- 整列（簡易オートレイアウト）
- 初期化（サンプルに戻す）
- Canvasズーム：Ctrl + マウスホイール

動作環境: Python 3.9+ / Tkinter
"""

import json
import math
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ---- Lane constants ----
LANE_META = -1  # 非賛否

# ---- Layout constants (logical units) ----
LANE_W = 260
GAP_X = 60
NODE_W = 240
NODE_H_MIN = 70
META_LEFT = 20
META_W = 260
GRID_Y = 18  # rough line height

# ---- Connectors (接続詞) -> semantics for lane placement ----
# mode:
#   "same" : same lane as parent
#   "next" : next lane (反論など)
#   "meta" : meta area
CONNECTOR_TO_RULE = {
    # same lane
    "なぜなら": ("premise", "same"),
    "たとえば": ("evidence", "same"),
    "加えて": ("addition", "same"),
    "つまり": ("clarification", "same"),
    # next lane (counter / rebuttal)
    "しかし": ("counter", "next"),
    "一方で": ("counter", "next"),
    "ただし": ("rebuttal", "next"),
    "それでも": ("rebuttal", "next"),
    # meta
    "前提として": ("assumption", "meta"),
    "定義として": ("definition", "meta"),
    "問いとして": ("question", "meta"),
    "補足として": ("clarification", "meta"),
    "別の観点で": ("issue_shift", "meta"),
}

EDITOR_CONNECTORS_MAIN = ["", "なぜなら", "たとえば", "加えて", "つまり", "しかし", "一方で", "ただし", "それでも"]
EDITOR_CONNECTORS_META = ["", "前提として", "定義として", "問いとして", "補足として", "別の観点で"]

ADD_CHOICES_MAIN = [
    "なぜなら", "たとえば", "加えて", "つまり",
    "しかし", "一方で", "ただし", "それでも",
    "前提として", "定義として", "問いとして", "補足として", "別の観点で",
]
ADD_CHOICES_META = ["定義として", "前提として", "問いとして", "補足として", "別の観点で"]


def sample_map():
    """Built-in sample: Kinoko vs Takenoko (expanded a bit)."""
    nodes = {}
    edges = []

    def nid():
        return uuid.uuid4().hex[:10]

    def add_node(lane, y, text, connector="", ntype=""):
        node_id = nid()
        nodes[node_id] = {
            "id": node_id,
            "lane": lane,
            "x": 0,
            "y": y,
            "connector": connector,
            "type": ntype,
            "text": text,
            "parent": "",
        }
        return node_id

    def link(a, b):
        edges.append({"source": a, "target": b})
        nodes[b]["parent"] = a

    # Meta: framing
    add_node(LANE_META, 60, "これは『きのこの山』と『たけのこの里』の好みを語る、平和な議論です。", "前提として", "assumption")
    add_node(LANE_META, 140, "評価軸は『味』『食感』『食べやすさ』『気分（思い出）』など複数あってOKです。", "定義として", "definition")
    add_node(LANE_META, 220, "あなたにとって『おいしい』の決め手は何ですか？", "問いとして", "question")
    add_node(LANE_META, 300, "論点がズレたら『別の観点で』として別枠に置き、無理に繋げません。", "補足として", "clarification")

    # Pro lane 0: きのこ派
    p0 = add_node(0, 80, "私は『きのこの山』派です。チョコとビスケットのバランスが良い。", "", "claim")
    p1 = add_node(0, 170, "サクサクしたクラッカー感が軽くて、何個でも食べられる。", "なぜなら", "premise"); link(p0, p1)
    p2 = add_node(0, 260, "チョコ部分が大きく感じて、満足感が出やすい。", "加えて", "addition"); link(p0, p2)
    p3 = add_node(0, 350, "コーヒー/紅茶と合わせると、甘さが引き立つ。", "たとえば", "evidence"); link(p0, p3)
    p4 = add_node(0, 440, "チョコが先に溶けるので『味の変化』が楽しい。", "加えて", "addition"); link(p0, p4)

    # Con lane 1: たけのこ派の反論
    c0 = add_node(1, 120, "私は『たけのこの里』派です。クッキーの一体感が強い。", "しかし", "counterclaim"); link(p0, c0)
    c1 = add_node(1, 210, "クッキー部分がしっとりしていて、チョコと馴染む。", "なぜなら", "premise"); link(c0, c1)
    c2 = add_node(1, 300, "形が持ちやすく、手が汚れにくい。", "加えて", "addition"); link(c0, c2)
    c3 = add_node(1, 390, "一口サイズで、食べやすさが高い。", "つまり", "clarification"); link(c0, c3)
    c4 = add_node(1, 480, "『満足感』は、クッキーの密度でこちらが勝つ。", "それでも", "rebuttal"); link(c0, c4)

    # Pro lane 2: 再主張
    r0 = add_node(2, 160, "確かに食べやすいが、『軽さ』はきのこが強い。", "ただし", "rebuttal"); link(c0, r0)
    r1 = add_node(2, 250, "チョコの主張が強いので、甘いもの欲が満たされる。", "なぜなら", "premise"); link(r0, r1)
    r2 = add_node(2, 340, "冷やすとチョコがパキッとして食感が増す。", "たとえば", "evidence"); link(r0, r2)
    r3 = add_node(2, 430, "『分離して食べる』など遊び方の幅がある。", "加えて", "addition"); link(r0, r3)

    # Con lane 3: 再反論
    rr0 = add_node(3, 200, "軽さより『一体感』の幸福度が大きい。", "一方で", "counterclaim"); link(r0, rr0)
    rr1 = add_node(3, 290, "チョコとクッキーの比率が計算されている。", "なぜなら", "premise"); link(rr0, rr1)
    rr2 = add_node(3, 380, "割れにくく、持ち運びにも向く。", "加えて", "addition"); link(rr0, rr2)

    # Meta: issue shift examples (NOT linked)
    add_node(LANE_META, 420, "価格・内容量・キャンペーン等も好みに影響するかもしれません。", "別の観点で", "issue_shift")
    add_node(LANE_META, 500, "子どもの頃の思い出（親が買ってくれた等）が好みを決める場合もあります。", "別の観点で", "issue_shift")

    return {"nodes": nodes, "edges": edges, "meta": {"title": "Kinoko vs Takenoko", "version": 1}}


class QuietMapApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("quiet map")
        self.geometry("1200x720")
        self.minsize(980, 620)

        self.scale = 1.0
        self.nodes = {}
        self.edges = []
        self.selected_id = ""
        self.drag_offset = (0, 0)
        self.dragging = False

        self._build_ui()
        self.reset_to_sample()

    def _build_ui(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=10)
        left.grid(row=0, column=0, sticky="nsw")

        ttk.Label(left, text="quiet map", font=("Meiryo UI", 14, "bold")).pack(anchor="w")

        btns = ttk.Frame(left)
        btns.pack(anchor="w", pady=(10, 6), fill="x")

        ttk.Button(btns, text="新規 賛成", command=lambda: self.add_root(lane=0)).grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=3)
        ttk.Button(btns, text="新規 反対", command=lambda: self.add_root(lane=1)).grid(row=0, column=1, sticky="ew", pady=3)

        ttk.Button(btns, text="新規 非賛否", command=self.add_meta).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=3)
        ttk.Button(btns, text="整列", command=self.align_now).grid(row=1, column=1, sticky="ew", pady=3)

        ttk.Button(btns, text="JSON保存", command=self.save_json).grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=3)
        ttk.Button(btns, text="JSON読込", command=self.load_json).grid(row=2, column=1, sticky="ew", pady=3)

        ttk.Button(btns, text="文章出力", command=self.export_paragraphs).grid(row=3, column=0, sticky="ew", padx=(0, 6), pady=3)
        ttk.Button(btns, text="初期化", command=self.reset_to_sample).grid(row=3, column=1, sticky="ew", pady=3)

        for c in (0, 1):
            btns.columnconfigure(c, weight=1)

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(left, text="選択ノード（詳細）", font=("Meiryo UI", 10, "bold")).pack(anchor="w")

        self.detail = tk.Text(left, width=34, height=18, wrap="word", font=("Meiryo UI", 10))
        self.detail.pack(fill="both", expand=False)
        self.detail.configure(state="disabled")

        ttk.Label(left, text="操作: 右クリック=追加/削除  ダブルクリック=編集\nCtrl+ホイール=ズーム", foreground="#444").pack(anchor="w", pady=(10, 0))

        right = ttk.Frame(self, padding=(0, 10, 10, 10))
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(right, bg="white", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        hsb = ttk.Scrollbar(right, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)

        self.canvas.bind("<Control-MouseWheel>", self.on_ctrl_wheel)
        self.canvas.bind("<Control-Button-4>", self.on_ctrl_wheel)
        self.canvas.bind("<Control-Button-5>", self.on_ctrl_wheel)

        self._context_menu = tk.Menu(self, tearoff=0)

    # ---- model ----
    def reset_to_sample(self):
        payload = sample_map()
        self.nodes = payload["nodes"]
        self.edges = payload["edges"]
        self.selected_id = ""
        self.scale = 1.0
        self.auto_layout()
        self.redraw()

    def add_root(self, lane):
        node_id = uuid.uuid4().hex[:10]
        self.nodes[node_id] = {
            "id": node_id,
            "lane": lane,
            "x": 0,
            "y": 60,
            "connector": "",
            "type": "claim",
            "text": "（ここに本文）",
            "parent": "",
        }
        self.selected_id = node_id
        self.auto_layout()
        self.redraw()

    def add_meta(self):
        node_id = uuid.uuid4().hex[:10]
        self.nodes[node_id] = {
            "id": node_id,
            "lane": LANE_META,
            "x": 0,
            "y": 60,
            "connector": "補足として",
            "type": "clarification",
            "text": "（ここに本文）",
            "parent": "",
        }
        self.selected_id = node_id
        self.auto_layout()
        self.redraw()

    def children_map(self):
        mp = {}
        for e in self.edges:
            mp.setdefault(e["source"], []).append(e["target"])
        return mp

    def add_child(self, parent_id, connector):
        if parent_id not in self.nodes:
            return
        parent = self.nodes[parent_id]
        if int(parent.get("lane", 0)) == LANE_META and (parent.get("type") or "") == "issue_shift":
            messagebox.showinfo("追加不可", "issue_shift ノードからは矢印で結ぶ追加はしません。")
            return

        ntype, mode = CONNECTOR_TO_RULE.get(connector, ("clarification", "same"))
        pl = int(parent.get("lane", 0))
        if mode == "meta":
            lane2 = LANE_META
        elif mode == "next":
            lane2 = pl + 1 if pl != LANE_META else 0
        else:
            lane2 = pl if pl != LANE_META else 0

        node_id = uuid.uuid4().hex[:10]
        self.nodes[node_id] = {
            "id": node_id,
            "lane": lane2,
            "x": 0,
            "y": int(parent.get("y", 0)) + 90,
            "connector": connector,
            "type": ntype,
            "text": "（ここに本文）",
            "parent": parent_id,
        }
        self.edges.append({"source": parent_id, "target": node_id})
        self.selected_id = node_id
        self.auto_layout()
        self.redraw()

    def delete_node(self, nid):
        if nid not in self.nodes:
            return
        children = self.children_map()
        to_delete = set()
        stack = [nid]
        while stack:
            x = stack.pop()
            if x in to_delete:
                continue
            to_delete.add(x)
            for c in children.get(x, []):
                stack.append(c)

        self.edges = [e for e in self.edges if e["source"] not in to_delete and e["target"] not in to_delete]
        for x in to_delete:
            self.nodes.pop(x, None)
        if self.selected_id in to_delete:
            self.selected_id = ""
        self.auto_layout()
        self.redraw()

    # ---- layout ----
    def lane_to_x(self, lane):
        if lane == LANE_META:
            return META_LEFT
        return META_LEFT + META_W + GAP_X + lane * (LANE_W + GAP_X)

    def estimate_h(self, text):
        s = (text or "").strip()
        if not s:
            return NODE_H_MIN
        lines = max(1, math.ceil(len(s) / 26))
        return NODE_H_MIN + (lines - 1) * GRID_Y

    def node_bbox(self, n):
        x1 = self.lane_to_x(int(n["lane"]))
        y1 = int(n["y"])
        w = (META_W - 20) if int(n["lane"]) == LANE_META else NODE_W
        h = max(NODE_H_MIN, self.estimate_h(n.get("text", "")))
        return x1, y1, x1 + w, y1 + h

    def auto_layout(self):
        lanes = {}
        for nid, n in self.nodes.items():
            lane = int(n.get("lane", 0))
            lanes.setdefault(lane, []).append(nid)

        for lane, ids in lanes.items():
            ids.sort(key=lambda i: int(self.nodes[i].get("y", 0)))
            y = 60
            step = 92 if lane != LANE_META else 86
            for i in ids:
                self.nodes[i]["y"] = y
                y += step

    def align_now(self):
        """整列ボタン用: レイアウトを計算して即座に再描画する。"""
        self.auto_layout()
        self.redraw()


    # ---- drawing ----
    def redraw(self):
        self.canvas.delete("all")
        self.draw_lanes()

        max_x = 0
        max_y = 0

        for e in self.edges:
            a = self.nodes.get(e["source"])
            b = self.nodes.get(e["target"])
            if not a or not b:
                continue
            ax1, ay1, ax2, ay2 = self.node_bbox(a)
            bx1, by1, bx2, by2 = self.node_bbox(b)
            x1 = ax2
            y1 = (ay1 + ay2) / 2
            x2 = bx1
            y2 = (by1 + by2) / 2
            self.draw_arrow(x1, y1, x2, y2)

        for nid, n in self.nodes.items():
            x1, y1, x2, y2 = self.node_bbox(n)
            max_x = max(max_x, x2)
            max_y = max(max_y, y2)
            is_sel = (nid == self.selected_id)
            outline = "#1f6feb" if is_sel else "#333"
            width = 2 if is_sel else 1
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=width, fill="white")

            lane = int(n.get("lane", 0))
            connector = (n.get("connector") or "").strip()
            title = connector if connector else ("非賛否" if lane == LANE_META else "")
            if title:
                self.canvas.create_text(x1 + 10, y1 + 12, anchor="w", text=title, font=("Meiryo UI", 10, "bold"))
            body = (n.get("text") or "").strip()
            self.canvas.create_text(x1 + 10, y1 + 32, anchor="nw", width=(x2 - x1 - 20), text=body, font=("Meiryo UI", 10))

        self.canvas.configure(scrollregion=(0, 0, max_x + 200, max_y + 200))
        self.refresh_detail()

    def draw_lanes(self):
        # meta band
        self.canvas.create_rectangle(META_LEFT, 20, META_LEFT + META_W, 10000, fill="#f4f4f4", outline="")
        self.canvas.create_text(META_LEFT + META_W / 2, 30, text="非賛否（前提/定義/問い/補足/論点切替）", font=("Meiryo UI", 10, "bold"))

        lanes = [int(n.get("lane", 0)) for n in self.nodes.values() if int(n.get("lane", 0)) != LANE_META]
        max_lane = max(lanes) if lanes else 3
        for lane in range(0, max_lane + 1):
            lx0 = self.lane_to_x(lane)
            lx1 = lx0 + LANE_W
            fill = "#eaf4ff" if lane % 2 == 0 else "#ffeef0"
            self.canvas.create_rectangle(lx0, 20, lx1, 10000, fill=fill, outline="")
            label = "賛成" if lane % 2 == 0 else "反対"
            self.canvas.create_text((lx0 + lx1) / 2, 30, text=f"{label}（列 {lane}）", font=("Meiryo UI", 10, "bold"))

    def draw_arrow(self, x1, y1, x2, y2):
        midx = (x1 + x2) / 2
        self.canvas.create_line(x1, y1, midx, y1, midx, y2, x2, y2, width=1, fill="#444", arrow=tk.LAST)

    # ---- events ----
    def hit_test_node(self, x, y):
        for nid, n in self.nodes.items():
            x1, y1, x2, y2 = self.node_bbox(n)
            if x1 <= x <= x2 and y1 <= y <= y2:
                return nid
        return ""

    def on_left_click(self, ev):
        x = self.canvas.canvasx(ev.x)
        y = self.canvas.canvasy(ev.y)
        nid = self.hit_test_node(x, y)
        self.selected_id = nid
        self.dragging = bool(nid)
        if nid:
            n = self.nodes[nid]
            x1, y1, x2, y2 = self.node_bbox(n)
            self.drag_offset = (x - x1, y - y1)
        self.redraw()

    def on_drag(self, ev):
        if not self.dragging or not self.selected_id:
            return
        x = self.canvas.canvasx(ev.x)
        y = self.canvas.canvasy(ev.y)
        n = self.nodes.get(self.selected_id)
        if not n:
            return
        n["y"] = max(40, int(y - self.drag_offset[1]))
        self.redraw()

    def on_release(self, ev):
        self.dragging = False

    def on_double_click(self, ev):
        x = self.canvas.canvasx(ev.x)
        y = self.canvas.canvasy(ev.y)
        nid = self.hit_test_node(x, y)
        if nid:
            self.selected_id = nid
            self.open_editor(nid)

    def on_right_click(self, ev):
        x = self.canvas.canvasx(ev.x)
        y = self.canvas.canvasy(ev.y)
        nid = self.hit_test_node(x, y)
        if not nid:
            return
        self.selected_id = nid
        self.redraw()

        n = self.nodes[nid]
        lane = int(n.get("lane", 0))
        ntype = (n.get("type") or "")

        self._context_menu.delete(0, tk.END)

        if lane == LANE_META and ntype == "issue_shift":
            self._context_menu.add_command(label="（issue_shift からは追加しません）", state="disabled")
        else:
            choices = ADD_CHOICES_META if lane == LANE_META else ADD_CHOICES_MAIN
            for conn in choices:
                self._context_menu.add_command(
                    label=f"追加: {conn}",
                    command=lambda c=conn, pid=nid: self.add_child(pid, c),
                )

        self._context_menu.add_separator()
        self._context_menu.add_command(label="削除", command=lambda pid=nid: self.delete_node(pid))
        self._context_menu.tk_popup(ev.x_root, ev.y_root)

    def on_ctrl_wheel(self, ev):
        delta = 0
        if hasattr(ev, "delta") and ev.delta:
            delta = ev.delta
        elif getattr(ev, "num", None) == 4:
            delta = 120
        elif getattr(ev, "num", None) == 5:
            delta = -120

        factor = 1.1 if delta > 0 else 1 / 1.1
        new_scale = max(0.6, min(2.2, self.scale * factor))
        if abs(new_scale - self.scale) < 1e-6:
            return
        self.scale = new_scale

        self.canvas.scale("all", 0, 0, factor, factor)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        for n in self.nodes.values():
            n["y"] = int(n.get("y", 0) * factor)
        self.redraw()

    # ---- editor ----
    def open_editor(self, nid):
        n = self.nodes.get(nid)
        if not n:
            return
        win = tk.Toplevel(self)
        win.title("ノード編集")
        win.geometry("560x420")
        win.minsize(520, 360)

        top = ttk.Frame(win, padding=10)
        top.pack(fill="x")

        lane = int(n.get("lane", 0))
        opts = EDITOR_CONNECTORS_META if lane == LANE_META else EDITOR_CONNECTORS_MAIN

        ttk.Label(top, text="接続詞").grid(row=0, column=0, sticky="w")
        var_conn = tk.StringVar(value=(n.get("connector") or ""))
        cmb = ttk.Combobox(top, textvariable=var_conn, values=opts, state="readonly", width=18)
        cmb.grid(row=0, column=1, sticky="w", padx=(8, 0))

        ttk.Label(top, text="本文").grid(row=1, column=0, sticky="nw", pady=(10, 0))

        txt = tk.Text(win, wrap="word", font=("Meiryo UI", 11))
        txt.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        txt.insert("1.0", n.get("text", ""))

        bottom = ttk.Frame(win, padding=(10, 0, 10, 10))
        bottom.pack(fill="x")

        def save():
            conn = var_conn.get().strip()
            n["connector"] = conn
            if conn in CONNECTOR_TO_RULE:
                ntype, mode = CONNECTOR_TO_RULE[conn]
                n["type"] = ntype
                pid = (n.get("parent") or "")
                if mode == "meta":
                    n["lane"] = LANE_META
                elif pid and pid in self.nodes and int(self.nodes[pid].get("lane", 0)) != LANE_META:
                    pl = int(self.nodes[pid].get("lane", 0))
                    n["lane"] = pl if mode == "same" else pl + 1
            n["text"] = txt.get("1.0", "end").strip()
            win.destroy()
            self.auto_layout()
            self.redraw()

        ttk.Button(bottom, text="キャンセル", command=win.destroy).pack(side="right")
        ttk.Button(bottom, text="保存", command=save).pack(side="right", padx=(0, 8))

    # ---- detail ----
    def refresh_detail(self):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        if self.selected_id and self.selected_id in self.nodes:
            n = self.nodes[self.selected_id]
            lane = int(n.get("lane", 0))
            label = "非賛否" if lane == LANE_META else ("賛成" if lane % 2 == 0 else "反対")
            self.detail.insert("end", f"ID: {n['id']}\n")
            self.detail.insert("end", f"列: {lane}（{label}）\n")
            self.detail.insert("end", f"接続詞: {n.get('connector','')}\n")
            self.detail.insert("end", f"type: {n.get('type','')}\n\n")
            self.detail.insert("end", "本文:\n")
            self.detail.insert("end", n.get("text", ""))
        else:
            self.detail.insert("end", "（ノード未選択）")
        self.detail.configure(state="disabled")

    # ---- save/load ----
    def save_json(self):
        path = filedialog.asksaveasfilename(title="JSON保存", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        payload = {"nodes": self.nodes, "edges": self.edges, "meta": {"app": "quiet-map", "version": 1}}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("保存", "保存しました。")

    def load_json(self):
        path = filedialog.askopenfilename(title="JSON読込", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            payload = json.loads(open(path, "r", encoding="utf-8").read())
            if not isinstance(payload.get("nodes"), dict) or not isinstance(payload.get("edges"), list):
                raise ValueError("nodes(dict) / edges(list) が見つかりません。")
            self.nodes = payload["nodes"]
            self.edges = payload["edges"]
            self.selected_id = ""
            self.auto_layout()
            self.redraw()
        except Exception as e:
            messagebox.showerror("読込エラー", str(e))

    # ---- paragraph export ----
    def export_paragraphs(self):
        children = {}
        targets = set()
        for e in self.edges:
            s = e.get("source"); t = e.get("target")
            if s and t:
                children.setdefault(s, []).append(t)
                targets.add(t)

        def ensure_sentence(s):
            s = (s or "").strip()
            if not s:
                return ""
            return s if s[-1] in "。！？!?" else s + "。"

        def sentence(nid):
            n = self.nodes[nid]
            conn = (n.get("connector") or "").strip()
            body = (n.get("text") or "").strip()
            if not body:
                return ""
            b = ensure_sentence(body)
            return f"{conn}、{b}" if conn else b

        roots = [nid for nid in self.nodes.keys() if nid not in targets]
        roots.sort(key=lambda nid: (0 if int(self.nodes[nid].get("lane", 0)) == LANE_META else 1,
                                   int(self.nodes[nid].get("lane", 0)) if int(self.nodes[nid].get("lane", 0)) != LANE_META else -1,
                                   int(self.nodes[nid].get("y", 0))))

        paragraphs = []
        visited = set()

        meta_nodes = [nid for nid, n in self.nodes.items() if int(n.get("lane", 0)) == LANE_META]
        meta_nodes.sort(key=lambda nid: int(self.nodes[nid].get("y", 0)))
        meta_para = []
        for nid in meta_nodes:
            n = self.nodes[nid]
            s = sentence(nid)
            if not s:
                continue
            if (n.get("type") or "") == "issue_shift":
                if meta_para:
                    paragraphs.append(meta_para); meta_para = []
                paragraphs.append([f"【別の観点】\n{s}"])
            else:
                meta_para.append(s)
        if meta_para:
            paragraphs.append(meta_para)

        def collect_same(start_id, lane):
            queue = [start_id]
            out = []
            while queue:
                nid = queue.pop(0)
                if nid in visited or nid not in self.nodes:
                    continue
                if int(self.nodes[nid].get("lane", 0)) != lane:
                    continue
                visited.add(nid)
                s = sentence(nid)
                if s:
                    out.append(s)
                kids = [c for c in children.get(nid, []) if c in self.nodes and int(self.nodes[c].get("lane", 0)) == lane]
                kids.sort(key=lambda c: int(self.nodes[c].get("y", 0)))
                queue[0:0] = kids
            return out

        def collect_next(from_id, lane):
            next_lane = lane + 1
            kids = [c for c in children.get(from_id, []) if c in self.nodes and int(self.nodes[c].get("lane", 0)) == next_lane]
            kids.sort(key=lambda c: int(self.nodes[c].get("y", 0)))
            for c in kids:
                para = collect_same(c, next_lane)
                if para:
                    paragraphs.append(para)
                collect_next(c, next_lane)

        for rid in roots:
            if rid not in self.nodes:
                continue
            if int(self.nodes[rid].get("lane", 0)) == LANE_META:
                continue
            lane = int(self.nodes[rid].get("lane", 0))
            para = collect_same(rid, lane)
            if para:
                paragraphs.append(para)
            collect_next(rid, lane)

        text = "\n\n".join(" ".join(p).strip() for p in paragraphs if p and " ".join(p).strip()).strip()
        if not text:
            text = "（本文が空のノードのみです）"

        win = tk.Toplevel(self)
        win.title("文章出力")
        win.geometry("720x520")

        t = tk.Text(win, wrap="word", font=("Meiryo UI", 11))
        t.pack(fill="both", expand=True, padx=10, pady=10)
        t.insert("1.0", text)

        bar = ttk.Frame(win, padding=(10, 0, 10, 10))
        bar.pack(fill="x")

        def save_txt():
            path = filedialog.asksaveasfilename(title="文章を保存", defaultextension=".txt", filetypes=[("Text", "*.txt")])
            if not path:
                return
            with open(path, "w", encoding="utf-8") as f:
                f.write(t.get("1.0", "end").strip())
            messagebox.showinfo("保存", "保存しました。")

        ttk.Button(bar, text="TXT保存", command=save_txt).pack(side="right")
        ttk.Button(bar, text="閉じる", command=win.destroy).pack(side="right", padx=(0, 8))


def main():
    QuietMapApp().mainloop()


if __name__ == "__main__":
    main()
