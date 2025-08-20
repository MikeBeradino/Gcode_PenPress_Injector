#!/usr/bin/env python3
"""
G-Code Pen Tool: Classic Z-press mode + Cleaning-pen mode

- Parses LightBurn/Marlin-style G-code where each "shape" is:
  M05 ; pen up
  G0 X... Y... [F...]
  G4 P...
  M03 ...
  G1 ...
  ...
  G0           <- blank G0 ends the shape
  G4 P...

- Classic (Z-press): insert initial pen-press routine and additional presses
  when cumulative drawn length > threshold (mm). Always M05+G4 between shapes.

- Cleaning pen: insert full cleaning routine (multi-tray cycles) after
  N marks and/or cumulative length > threshold. Always M05+G4 between shapes.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import math
import re

# ---------- Helpers ----------

FLOAT = r"[-+]?[0-9]*\.?[0-9]+"

def extract_xy(line, last_x=None, last_y=None):
    x = re.search(rf"X({FLOAT})", line)
    y = re.search(rf"Y({FLOAT})", line)
    xv = float(x.group(1)) if x else last_x
    yv = float(y.group(1)) if y else last_y
    return xv, yv

# ---------- GUI App ----------

class GCodePenTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("G-Code Pen Tool (Classic + Cleaning)")
        self.geometry("720x520")

        # --- Mode selection ---
        mode_frame = tk.Frame(self, padx=10, pady=8)
        mode_frame.pack(fill=tk.X)
        tk.Label(mode_frame, text="Pen Mode:").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="classic")
        tk.Radiobutton(mode_frame, text="Classic (Z-press)", variable=self.mode_var, value="classic",
                       command=self._refresh_state).pack(side=tk.LEFT, padx=8)
        tk.Radiobutton(mode_frame, text="Cleaning Pen (servo clean)", variable=self.mode_var, value="cleaning",
                       command=self._refresh_state).pack(side=tk.LEFT, padx=8)

        # --- Common parameters ---
        common = tk.LabelFrame(self, text="Common", padx=10, pady=8)
        common.pack(fill=tk.X, padx=10)

        tk.Label(common, text="Between-shape up pause (ms):").grid(row=0, column=0, sticky=tk.W)
        self.between_pause_ms = tk.Entry(common, width=8)
        self.between_pause_ms.insert(0, "450")
        self.between_pause_ms.grid(row=0, column=1, sticky=tk.W, padx=(4, 12))

        tk.Label(common, text="Cumulative length threshold (mm):").grid(row=0, column=2, sticky=tk.W)
        self.cum_len_threshold = tk.Scale(common, from_=0, to=2000, orient=tk.HORIZONTAL)
        self.cum_len_threshold.set(200)
        self.cum_len_threshold.grid(row=0, column=3, sticky=tk.EW)
        common.grid_columnconfigure(3, weight=1)

        # --- Classic params ---
        classic = tk.LabelFrame(self, text="Classic (Z-press) Parameters", padx=10, pady=8)
        classic.pack(fill=tk.X, padx=10, pady=(6,0))
        self.classic_frame = classic

        tk.Label(classic, text="Pen Down Z (mm):").grid(row=0, column=0, sticky=tk.W)
        self.pen_down_z = tk.Entry(classic, width=8); self.pen_down_z.insert(0, "5"); self.pen_down_z.grid(row=0, column=1, sticky=tk.W)

        tk.Label(classic, text="Pen Up Z (mm):").grid(row=0, column=2, sticky=tk.W)
        self.pen_up_z = tk.Entry(classic, width=8); self.pen_up_z.insert(0, "10"); self.pen_up_z.grid(row=0, column=3, sticky=tk.W)

        tk.Label(classic, text="Drawing Height Z (mm):").grid(row=0, column=4, sticky=tk.W)
        self.draw_height_z = tk.Entry(classic, width=8); self.draw_height_z.insert(0, "35"); self.draw_height_z.grid(row=0, column=5, sticky=tk.W)

        tk.Label(classic, text="Pen-press X:").grid(row=1, column=0, sticky=tk.W, pady=(6,0))
        self.press_x = tk.Entry(classic, width=8); self.press_x.insert(0, "5"); self.press_x.grid(row=1, column=1, sticky=tk.W, pady=(6,0))

        tk.Label(classic, text="Pen-press Y:").grid(row=1, column=2, sticky=tk.W, pady=(6,0))
        self.press_y = tk.Entry(classic, width=8); self.press_y.insert(0, "5"); self.press_y.grid(row=1, column=3, sticky=tk.W, pady=(6,0))

        # --- Cleaning-pen params ---
        cleaning = tk.LabelFrame(self, text="Cleaning Pen Parameters", padx=10, pady=8)
        cleaning.pack(fill=tk.X, padx=10, pady=(6,0))
        self.cleaning_frame = cleaning

        tk.Label(cleaning, text="Initial clean at start:").grid(row=0, column=0, sticky=tk.W)
        self.initial_clean_var = tk.BooleanVar(value=False)
        tk.Checkbutton(cleaning, variable=self.initial_clean_var).grid(row=0, column=1, sticky=tk.W)

        tk.Label(cleaning, text="Clean every N marks (0=off):").grid(row=0, column=2, sticky=tk.W)
        self.clean_every_marks = tk.Entry(cleaning, width=8); self.clean_every_marks.insert(0, "0"); self.clean_every_marks.grid(row=0, column=3, sticky=tk.W)

        tk.Label(cleaning, text="OR clean after length (mm, 0=off):").grid(row=0, column=4, sticky=tk.W)
        self.clean_after_mm = tk.Entry(cleaning, width=8); self.clean_after_mm.insert(0, "0"); self.clean_after_mm.grid(row=0, column=5, sticky=tk.W)

        tk.Label(cleaning, text="Tray base X:").grid(row=1, column=0, sticky=tk.W, pady=(6,0))
        self.clean_x = tk.Entry(cleaning, width=8); self.clean_x.insert(0, "5"); self.clean_x.grid(row=1, column=1, sticky=tk.W, pady=(6,0))

        tk.Label(cleaning, text="Tray Ys (comma list):").grid(row=1, column=2, sticky=tk.W, pady=(6,0))
        self.clean_ys = tk.Entry(cleaning, width=18); self.clean_ys.insert(0, "0,25,55,65"); self.clean_ys.grid(row=1, column=3, sticky=tk.W, pady=(6,0))

        tk.Label(cleaning, text="Clean Z travel (mm):").grid(row=1, column=4, sticky=tk.W, pady=(6,0))
        self.clean_z = tk.Entry(cleaning, width=8); self.clean_z.insert(0, "25"); self.clean_z.grid(row=1, column=5, sticky=tk.W, pady=(6,0))

        tk.Label(cleaning, text="Down dwell (ms):").grid(row=2, column=0, sticky=tk.W, pady=(6,0))
        self.clean_down_ms = tk.Entry(cleaning, width=8); self.clean_down_ms.insert(0, "1000"); self.clean_down_ms.grid(row=2, column=1, sticky=tk.W, pady=(6,0))

        tk.Label(cleaning, text="Up dwell (ms):").grid(row=2, column=2, sticky=tk.W, pady=(6,0))
        self.clean_up_ms = tk.Entry(cleaning, width=8); self.clean_up_ms.insert(0, "450"); self.clean_up_ms.grid(row=2, column=3, sticky=tk.W, pady=(6,0))

        tk.Label(cleaning, text="Cycles per tray:").grid(row=2, column=4, sticky=tk.W, pady=(6,0))
        self.cycles_per_tray = tk.Entry(cleaning, width=8); self.cycles_per_tray.insert(0, "2"); self.cycles_per_tray.grid(row=2, column=5, sticky=tk.W, pady=(6,0))

        # --- File controls ---
        files = tk.Frame(self, padx=10, pady=10)
        files.pack(fill=tk.X)
        self.file_label = tk.Label(files, text="No file selected")
        self.file_label.pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(files, text="Select G-code File", command=self.select_file).pack(side=tk.LEFT, padx=(8,8))
        tk.Button(files, text="Process File", command=self.process_file).pack(side=tk.RIGHT)

        self.selected_file = None
        self._refresh_state()

    def _refresh_state(self):
        mode = self.mode_var.get()
        # Enable/disable frames by mode
        state_classic = tk.NORMAL if mode == "classic" else tk.DISABLED
        state_clean = tk.NORMAL if mode == "cleaning" else tk.DISABLED
        for child in self.classic_frame.winfo_children():
            child.configure(state=state_classic)
        for child in self.cleaning_frame.winfo_children():
            child.configure(state=state_clean)

    def select_file(self):
        path = filedialog.askopenfilename(
            title="Select G-code File",
            filetypes=[("G-code Files", "*.gc *.gcode *.nc *.txt"), ("All Files", "*.*")]
        )
        if path:
            self.selected_file = path
            self.file_label.config(text=path)

    # ---------- Core parsing ----------

    def parse_shapes(self, lines):
        """
        Returns list of dicts:
          {'m05_idx': int, 'start': int, 'end': int, 'length': float}
        where:
          - m05_idx is line index of the reposition 'M05' before the shape
          - start is index of the 'M03...' line
          - end is index of the blank 'G0' (and its following 'G4', if any)
          - length is total Euclidean G1 length
        """
        shapes = []
        for i, ln in enumerate(lines):
            if ln.strip().startswith("M03"):
                # find prior M05 (start of reposition block)
                j = i - 1
                while j >= 0 and not lines[j].strip().startswith("M05"):
                    j -= 1
                if j < 0:
                    continue
                # find end: blank G0 (no X/Y), include following G4 pause if present
                k = i + 1
                end = i
                while k < len(lines):
                    l = lines[k].strip()
                    if l.startswith("G0") and ('X' not in l and 'Y' not in l):
                        end = k
                        if k + 1 < len(lines) and lines[k + 1].strip().startswith("G4"):
                            end = k + 1
                        break
                    k += 1
                # compute path length
                # start coords from G0 after the M05
                if j + 1 >= len(lines):
                    continue
                sx, sy = extract_xy(lines[j + 1])
                if sx is None or sy is None:
                    continue
                last_x, last_y = sx, sy
                length = 0.0
                for seg in lines[i + 1: end + 1]:
                    if seg.strip().startswith("G1"):
                        nx, ny = extract_xy(seg, last_x, last_y)
                        length += math.hypot((nx - last_x), (ny - last_y))
                        last_x, last_y = nx, ny
                shapes.append({'m05_idx': j, 'start': i, 'end': end, 'length': length})
        return shapes

    # ---------- Routines ----------

    def make_between_shape_lift(self, up_ms):
        return [ "M05 ; pen up\n", f"G4 P{int(up_ms)} ; pause\n" ]

    def make_pen_press_classic(self, pen_x, pen_y, z_up, z_down, z_draw, up_ms, comment=None):
        out = ["G90\n", "M05 ; pen up\n", f"G0 X{pen_x} Y{pen_y}\n", f"G4 P{int(up_ms)} ; pause\n"]
        if comment:
            out.append(f"; {comment}\n")
        for _ in range(3):
            out.append(f"G0 Z{z_up} F3000\n")
            out.append(f"G0 Z{z_down} F3000\n")
        out.append(f"G0 Z{z_draw} F3000\n")
        out.append("M05 ; pen up\n")
        out.append(f"G4 P{int(up_ms)} ; pause\n")
        return out

    def make_cleaning_routine(self, x_base, ys, z_travel, down_ms, up_ms, cycles_per_tray):
        """
        Mirrors the sample routine; visits each tray Y and toggles M03/M05 with dwells,
        includes M400 waits around tray moves.
        """
        out = ["G90\n", "M05 ; pen up\n", f"G4 P{int(up_ms)} ; pause\n"]
        for y in ys:
            out.append(f"G0 X{x_base} Y{y} Z{z_travel} F3000\n")
            out.append("M400\n")
            for _ in range(int(cycles_per_tray)):
                out.append("M03 ; pen down\n")
                out.append(f"G4 P{int(down_ms)} ; pause\n")
                out.append("M05 ; pen up\n")
                out.append(f"G4 P{int(up_ms)} ; pause\n")
            out.append("M400\n")
        return out

    # ---------- Processing ----------

    def process_file(self):
        try:
            up_pause_ms = int(float(self.between_pause_ms.get()))
            cum_threshold = float(self.cum_len_threshold.get())
            mode = self.mode_var.get()
        except Exception:
            messagebox.showerror("Error", "Please check common parameter values.")
            return

        if not self.selected_file:
            messagebox.showwarning("No file", "Select a G-code file first.")
            return


        with open(self.selected_file, "r") as f:
            lines = f.readlines()

        shapes = self.parse_shapes(lines)
        if not shapes:
            messagebox.showerror("No shapes", "No pen-down shapes (M03 ... G1 ... G0) found.")
            return

        output = []
        header_end = shapes[0]['m05_idx']
        output.extend(lines[:header_end])  # keep header before first reposition M05

        # Mode: Classic (Z-press)
        if mode == "classic":
            try:
                z_down = float(self.pen_down_z.get())
                z_up = float(self.pen_up_z.get())
                z_draw = float(self.draw_height_z.get())
                px = float(self.press_x.get())
                py = float(self.press_y.get())
            except Exception:
                messagebox.showerror("Error", "Check Classic (Z) parameter values.")
                return

            # Initial press
            output.extend(self.make_pen_press_classic(px, py, z_up, z_down, z_draw, up_pause_ms))

            cumulative = 0.0
            for idx, sh in enumerate(shapes):
                # Always lift between shapes
                if idx > 0:
                    output.extend(self.make_between_shape_lift(up_pause_ms))
                # Threshold press before next shape if cumulative > threshold (use last cumulative)
                if idx > 0 and cumulative > cum_threshold:
                    output.extend(self.make_pen_press_classic(px, py, z_up, z_down, z_draw, up_pause_ms,
                                                              comment=f"Threshold reached: {cumulative:.2f} mm > {cum_threshold:.2f} mm"))
                    cumulative = 0.0
                # Reposition block (drop original M05)
                output.extend(lines[sh['m05_idx'] + 1: sh['start']])
                # Shape (M03.. to G0(blank) [+optional G4])
                output.extend(lines[sh['start']: sh['end'] + 1])
                cumulative += sh['length']

            output.extend(lines[shapes[-1]['end'] + 1:])

        # Mode: Cleaning pen
        else:
            try:
                initial_clean = bool(self.initial_clean_var.get())
                clean_every = int(float(self.clean_every_marks.get()))
                clean_after_mm = float(self.clean_after_mm.get())
                cx = float(self.clean_x.get())
                ys = [float(y.strip()) for y in self.clean_ys.get().split(",") if y.strip() != ""]
                cz = float(self.clean_z.get())
                c_down_ms = int(float(self.clean_down_ms.get()))
                c_up_ms = int(float(self.clean_up_ms.get()))
                cycles = int(float(self.cycles_per_tray.get()))
            except Exception:
                messagebox.showerror("Error", "Check Cleaning-pen parameter values.")
                return

            # Optional initial clean
            if initial_clean:
                output.extend(self.make_cleaning_routine(cx, ys, cz, c_down_ms, c_up_ms, cycles))

            marks_since = 0
            length_since = 0.0
            for idx, sh in enumerate(shapes):
                # Always lift between shapes
                if idx > 0:
                    output.extend(self.make_between_shape_lift(up_pause_ms))

                # Clean if cadence hit (either rule can trigger)
                do_clean = False
                if clean_every > 0 and marks_since >= clean_every:
                    do_clean = True
                if clean_after_mm > 0 and length_since > clean_after_mm:
                    do_clean = True
                if do_clean:
                    output.extend(self.make_cleaning_routine(cx, ys, cz, c_down_ms, c_up_ms, cycles))
                    marks_since = 0
                    length_since = 0.0

                # Reposition (drop original M05)
                output.extend(lines[sh['m05_idx'] + 1: sh['start']])
                # Shape
                output.extend(lines[sh['start']: sh['end'] + 1])

                # Update counters
                marks_since += 1
                length_since += sh['length']

            output.extend(lines[shapes[-1]['end'] + 1:])

        out_path = self.selected_file.rsplit(".", 1)[0] + "_processed.gcode"
        with open(out_path, "w") as f:
            f.writelines(output)
        messagebox.showinfo("Done", f"Processed file saved to:\n{out_path}")


if __name__ == "__main__":
    app = GCodePenTool()
    app.mainloop()
