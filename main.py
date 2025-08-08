import tkinter as tk
from tkinter import filedialog, messagebox
import math
import re


class GCodePenPressTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("G-Code Pen Press Utility")

        # --- UI for pen press parameters ---
        params_frame = tk.Frame(self, padx=10, pady=10)
        params_frame.pack(fill=tk.X)

        tk.Label(params_frame, text="Pen Down Z (mm):").grid(row=0, column=0, sticky=tk.W)
        self.pen_down_entry = tk.Entry(params_frame)
        self.pen_down_entry.insert(0, "5")
        self.pen_down_entry.grid(row=0, column=1, sticky=tk.EW)

        tk.Label(params_frame, text="Pen Up Z (mm):").grid(row=1, column=0, sticky=tk.W)
        self.pen_up_entry = tk.Entry(params_frame)
        self.pen_up_entry.insert(0, "10")
        self.pen_up_entry.grid(row=1, column=1, sticky=tk.EW)

        tk.Label(params_frame, text="Drawing Height Z (mm):").grid(row=2, column=0, sticky=tk.W)
        self.drawing_height_entry = tk.Entry(params_frame)
        self.drawing_height_entry.insert(0, "35")
        self.drawing_height_entry.grid(row=2, column=1, sticky=tk.EW)

        tk.Label(params_frame, text="Pen Press X (mm):").grid(row=3, column=0, sticky=tk.W)
        self.pen_x_entry = tk.Entry(params_frame)
        self.pen_x_entry.insert(0, "5")
        self.pen_x_entry.grid(row=3, column=1, sticky=tk.EW)

        tk.Label(params_frame, text="Pen Press Y (mm):").grid(row=4, column=0, sticky=tk.W)
        self.pen_y_entry = tk.Entry(params_frame)
        self.pen_y_entry.insert(0, "5")
        self.pen_y_entry.grid(row=4, column=1, sticky=tk.EW)

        # --- Threshold slider ---
        slider_frame = tk.Frame(self, padx=10, pady=10)
        slider_frame.pack(fill=tk.X)
        tk.Label(slider_frame, text="Pen Press Threshold (mm):").pack(anchor=tk.W)
        self.threshold_slider = tk.Scale(slider_frame, from_=0, to=1000, orient=tk.HORIZONTAL)
        self.threshold_slider.set(200)
        self.threshold_slider.pack(fill=tk.X)

        # --- File controls ---
        btn_frame = tk.Frame(self, padx=10, pady=10)
        btn_frame.pack(fill=tk.X)
        self.file_label = tk.Label(btn_frame, text="No file selected")
        self.file_label.pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(btn_frame, text="Select G-code File", command=self.select_file).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_frame, text="Process File", command=self.process_file).pack(side=tk.RIGHT)

    def select_file(self):
        path = filedialog.askopenfilename(
            title="Select G-code File",
            filetypes=[("G-code Files", "*.gc *.gcode"), ("All Files", "*.*")]
        )
        if path:
            self.selected_file = path
            self.file_label.config(text=path)

    def process_file(self):
        # get parameters
        pen_down_z = float(self.pen_down_entry.get())
        pen_up_z = float(self.pen_up_entry.get())
        drawing_height_z = float(self.drawing_height_entry.get())
        pen_x = float(self.pen_x_entry.get())
        pen_y = float(self.pen_y_entry.get())
        threshold = float(self.threshold_slider.get())

        file_path = getattr(self, 'selected_file', None)
        if not file_path:
            messagebox.showwarning("No file", "Select a G-code file first.")
            return

        lines = open(file_path).readlines()

        # parse shapes
        shapes = []
        for i, ln in enumerate(lines):
            if ln.strip().startswith("M03"):
                j = i - 1
                while j >= 0 and not lines[j].strip().startswith("M05"): j -= 1
                if j < 0: continue
                # find shape end
                k = i + 1
                end = i
                while k < len(lines):
                    l = lines[k].strip()
                    if l.startswith("G0") and 'X' not in l and 'Y' not in l:
                        end = k + (1 if k + 1 < len(lines) and lines[k + 1].strip().startswith("G4") else 0)
                        break
                    k += 1
                # compute length
                mx = re.search(r"X([-+]?[0-9]*\.?[0-9]+)", lines[j + 1])
                my = re.search(r"Y([-+]?[0-9]*\.?[0-9]+)", lines[j + 1])
                if not (mx and my): continue
                last_x, last_y = float(mx.group(1)), float(my.group(1))
                length = 0.0
                for seg in lines[i + 1:end + 1]:
                    if seg.strip().startswith("G1"):
                        xm = re.search(r"X([-+]?[0-9]*\.?[0-9]+)", seg)
                        ym = re.search(r"Y([-+]?[0-9]*\.?[0-9]+)", seg)
                        x = float(xm.group(1)) if xm else last_x
                        y = float(ym.group(1)) if ym else last_y
                        length += math.hypot(x - last_x, y - last_y)
                        last_x, last_y = x, y
                shapes.append({'m05_idx': j, 'start': i, 'end': end, 'length': length})

        if not shapes:
            messagebox.showerror("No shapes", "No pen-down shapes found.")
            return

        def make_pen_press(cum_length=None):
            routine = [
                "G90\n",
                "M05 ; pen up\n",
                f"G0 X{pen_x} Y{pen_y}\n",
                "G4 P450 ; pause\n"
            ]
            if cum_length is not None:
                routine.append(f"; Threshold reached: cumulative {cum_length:.2f} mm > {threshold:.2f} mm\n")
            for _ in range(3):
                routine.append(f"G0 Z{pen_up_z} F3000\n")
                routine.append(f"G0 Z{pen_down_z} F3000\n")
            routine.append(f"G0 Z{drawing_height_z} F3000\n")
            routine.append("M05 ; pen up\n")
            routine.append("G4 P450 ; pause\n")
            return routine

        output = []
        hdr_end = shapes[0]['m05_idx']
        output.extend(lines[:hdr_end])
        output.extend(make_pen_press())  # initial press

        cumulative = 0.0
        for idx, shape in enumerate(shapes):
            if idx > 0:
                output.append("M05 ; pen up\n")
                output.append("G4 P450 ; pause\n")

            if idx > 0 and cumulative > threshold:
                output.extend(make_pen_press(cumulative))
                cumulative = 0.0

            output.extend(lines[shape['m05_idx'] + 1: shape['start']])
            output.extend(lines[shape['start']: shape['end'] + 1])
            cumulative += shape['length']

        output.extend(lines[shapes[-1]['end'] + 1:])

        out_path = file_path.rsplit('.', 1)[0] + '_processed.gc'
        with open(out_path, 'w') as f:
            f.writelines(output)

        messagebox.showinfo("Done", f"Processed file saved to:\n{out_path}")



if __name__ == "__main__":
    app = GCodePenPressTool()
    app.mainloop()
