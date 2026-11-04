"""
Gegenwichte Widget – calcolatore dell'orario di uscita dal lavoro.

Un piccolo widget desktop frameless, trascinabile, ispirato alle composizioni
geometriche di Kandinsky ("Gegenwichte", 1926): cerchi che si bilanciano,
diagonali tese, una griglia di quadrati, fondo caldo.

Usa SOLO la libreria standard di Python (tkinter + json): nessun pip install.

Logica:
    uscita = entrata + ORE_LAVORO + max(rientro_pausa - uscita_pausa, PAUSA_MINIMA)

I tre orari inseriti e la posizione della finestra vengono salvati in un file
JSON nella cartella utente e ricaricati alla riapertura.
"""

import json
import os
import tkinter as tk
from datetime import timedelta
from tkinter import font as tkfont

# ---------------------------------------------------------------------------
# CONFIGURAZIONE – modifica qui il monte ore giornaliero (in minuti).
# Es.: 8 ore = 8 * 60 ; 7 ore e 36 minuti = 7 * 60 + 36
# ---------------------------------------------------------------------------
ORE_LAVORO_MINUTI = 8 * 60

# Pausa minima: se la pausa reale e' piu' breve, viene contata comunque cosi'.
PAUSA_MINIMA_MINUTI = 30

# File di salvataggio (nella home dell'utente, es. C:\Users\Nome\.gegenwichte.json)
FILE_SALVATAGGIO = os.path.join(os.path.expanduser("~"), ".gegenwichte.json")

# Palette: fondo caldo, blu profondo, rosso, giallo, tortora.
C_FONDO = "#E9DFC8"      # avorio caldo (tela)
C_BLU = "#1F2A44"        # blu notte (cerchio grande)
C_ROSSO = "#C8352B"      # rosso
C_GIALLO = "#E8B32E"     # giallo ocra
C_NERO = "#1A1715"       # nero caldo (linee)
C_CELESTE = "#7FA7C9"    # celeste polveroso
C_TORTORA = "#B9AC94"    # tortora (griglia)
C_CAMPO = "#F6F0E2"      # fondo caselle
C_TESTO = "#1A1715"

LARGHEZZA, ALTEZZA = 560, 190


class GegenwichteWidget(tk.Tk):
    """Finestra principale del widget."""

    def __init__(self):
        super().__init__()
        self.title("Gegenwichte")
        self.overrideredirect(True)          # niente barra del titolo di Windows
        self.resizable(False, False)
        self.configure(bg=C_FONDO)
        self.attributes("-topmost", False)

        self._drag_x = 0
        self._drag_y = 0
        self._stato = self._carica_stato()

        # Posizione iniziale: quella salvata, oppure in basso a destra.
        x = self._stato.get("x", self.winfo_screenwidth() - LARGHEZZA - 40)
        y = self._stato.get("y", self.winfo_screenheight() - ALTEZZA - 100)
        self.geometry(f"{LARGHEZZA}x{ALTEZZA}+{x}+{y}")

        self._crea_grafica()
        self._crea_campi()
        self._ripristina_valori()
        self._calcola()

        # Chiusura ordinata anche con Alt+F4 (quando disponibile).
        self.protocol("WM_DELETE_WINDOW", self._chiudi)
        # Ripristina lo stile frameless quando la finestra torna dall'icona.
        self.bind("<Map>", self._su_ripristino)

    # ------------------------------------------------------------------ #
    # GRAFICA: la "tela" alla Kandinsky disegnata su un Canvas
    # ------------------------------------------------------------------ #
    def _crea_grafica(self):
        self.tela = tk.Canvas(
            self, width=LARGHEZZA, height=ALTEZZA, bg=C_FONDO,
            highlightthickness=0, bd=0
        )
        self.tela.place(x=0, y=0)
        c = self.tela

        # Cornice nera sottile che "chiude" il quadro.
        c.create_rectangle(2, 2, LARGHEZZA - 2, ALTEZZA - 2, outline=C_NERO, width=2)

        # Griglia di quadratini a sinistra (contrappeso "leggero").
        for riga in range(3):
            for col in range(3):
                x0 = 70 + col * 14
                y0 = 132 + riga * 14
                colore = C_TORTORA if (riga + col) % 2 == 0 else C_FONDO
                c.create_rectangle(x0, y0, x0 + 12, y0 + 12, fill=colore, outline=C_NERO)

        # Cerchio grande blu in alto a sinistra (il "peso" principale).
        c.create_oval(44, 18, 118, 92, fill=C_BLU, outline="")
        c.create_oval(58, 30, 84, 56, fill=C_CELESTE, outline="")   # luna interna

        # Cerchio rosso piccolo che lo bilancia a destra.
        c.create_oval(466, 118, 500, 152, fill=C_ROSSO, outline="")

        # Semicerchio giallo in basso a destra.
        c.create_arc(420, 150, 500, 230, start=0, extent=180, fill=C_GIALLO, outline="")

        # Due diagonali tese che attraversano la composizione.
        c.create_line(130, 170, 440, 22, fill=C_NERO, width=2)
        c.create_line(150, 178, 456, 34, fill=C_NERO, width=1)

        # Triangolo aperto, solo contorno.
        c.create_polygon(420, 24, 455, 24, 437, 60, outline=C_NERO, fill="", width=1)

        # Manopola SINISTRA: riduci a icona (gialla).
        self._manopola(26, ALTEZZA // 2, C_GIALLO, "–", self._riduci)
        # Manopola DESTRA: chiudi (rossa).
        self._manopola(LARGHEZZA - 26, ALTEZZA // 2, C_ROSSO, "×", self._chiudi)

        # Trascinamento dal corpo del widget.
        c.bind("<ButtonPress-1>", self._inizio_trascinamento)
        c.bind("<B1-Motion>", self._trascina)

    def _manopola(self, cx, cy, colore, simbolo, comando):
        """Disegna una manopola rotonda stile hardware e le associa un comando."""
        r = 16
        tag = f"manopola_{simbolo}"
        # Ombra, corpo, riflesso.
        self.tela.create_oval(cx - r + 2, cy - r + 3, cx + r + 2, cy + r + 3,
                              fill="#C9BBA0", outline="", tags=tag)
        self.tela.create_oval(cx - r, cy - r, cx + r, cy + r,
                              fill=colore, outline=C_NERO, width=2, tags=tag)
        self.tela.create_oval(cx - 6, cy - 9, cx + 2, cy - 3,
                              fill="#FFFFFF", outline="", stipple="gray50", tags=tag)
        self.tela.create_text(cx, cy + 1, text=simbolo, fill=C_NERO,
                              font=("Segoe UI", 13, "bold"), tags=tag)

        self.tela.tag_bind(tag, "<Button-1>", lambda e: comando())
        self.tela.tag_bind(tag, "<Enter>", lambda e: self.tela.config(cursor="hand2"))
        self.tela.tag_bind(tag, "<Leave>", lambda e: self.tela.config(cursor=""))

    # ------------------------------------------------------------------ #
    # CAMPI DI INPUT / OUTPUT
    # ------------------------------------------------------------------ #
    def _crea_campi(self):
        f_label = tkfont.Font(family="Segoe UI", size=8)
        f_campo = tkfont.Font(family="Consolas", size=15, weight="bold")

        # Validazione: solo cifre e ":" al massimo 5 caratteri (HH:MM).
        valida = (self.register(self._valida_input), "%P")

        etichette = ["Entrata", "Pausa – uscita", "Pausa – rientro", "Uscita"]
        self.var = [tk.StringVar() for _ in range(4)]
        self.campi = []

        x_base, passo, y = 150, 100, 72
        for i, testo in enumerate(etichette):
            tk.Label(self, text=testo, bg=C_FONDO, fg=C_TESTO, font=f_label)\
                .place(x=x_base + i * passo, y=y - 22, anchor="w")

            if i < 3:
                campo = tk.Entry(
                    self, textvariable=self.var[i], width=5, font=f_campo,
                    bg=C_CAMPO, fg=C_TESTO, relief="flat", justify="center",
                    insertbackground=C_TESTO, validate="key", validatecommand=valida,
                    highlightthickness=2, highlightbackground=C_NERO,
                    highlightcolor=C_ROSSO,
                )
                campo.bind("<KeyRelease>", lambda e: self._calcola())
                campo.bind("<FocusOut>", lambda e: self._normalizza_e_calcola())
            else:
                # Casella di solo output: bordo blu, testo blu, non modificabile.
                campo = tk.Entry(
                    self, textvariable=self.var[i], width=5, font=f_campo,
                    bg=C_CAMPO, fg=C_BLU, relief="flat", justify="center",
                    state="readonly", readonlybackground=C_CAMPO,
                    highlightthickness=2, highlightbackground=C_BLU,
                    highlightcolor=C_BLU,
                )
            campo.place(x=x_base + i * passo, y=y, anchor="w")
            self.campi.append(campo)

        # Didascalia con il monte ore attivo.
        ore, minuti = divmod(ORE_LAVORO_MINUTI, 60)
        tk.Label(self, text=f"{ore}h{minuti:02d} nette · pausa min {PAUSA_MINIMA_MINUTI}' · trascina per spostare",
                 bg=C_FONDO, fg=C_TORTORA, font=("Segoe UI", 7))\
            .place(x=150, y=118, anchor="w")

        # Anche le etichette permettono il trascinamento.
        for w in self.winfo_children():
            if isinstance(w, tk.Label):
                w.bind("<ButtonPress-1>", self._inizio_trascinamento)
                w.bind("<B1-Motion>", self._trascina)

    @staticmethod
    def _valida_input(testo):
        """Accetta solo cifre e ':' fino a 5 caratteri."""
        return len(testo) <= 5 and all(ch.isdigit() or ch == ":" for ch in testo)

    # ------------------------------------------------------------------ #
    # LOGICA DI CALCOLO
    # ------------------------------------------------------------------ #
    @staticmethod
    def _a_minuti(testo):
        """'08:30' -> 510 ; '830' -> 510 ; restituisce None se non valido."""
        testo = testo.strip()
        if ":" in testo:
            parti = testo.split(":")
            if len(parti) != 2 or not all(p.isdigit() for p in parti):
                return None
            h, m = int(parti[0]), int(parti[1])
        elif testo.isdigit() and 3 <= len(testo) <= 4:
            h, m = int(testo[:-2]), int(testo[-2:])
        else:
            return None
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h * 60 + m
        return None

    @staticmethod
    def _a_testo(minuti):
        minuti %= 24 * 60
        return f"{minuti // 60:02d}:{minuti % 60:02d}"

    def _normalizza_e_calcola(self):
        """Riscrive i campi nel formato HH:MM (es. '830' -> '08:30')."""
        for i in range(3):
            m = self._a_minuti(self.var[i].get())
            if m is not None:
                self.var[i].set(self._a_testo(m))
        self._calcola()

    def _calcola(self):
        entrata = self._a_minuti(self.var[0].get())
        p_uscita = self._a_minuti(self.var[1].get())
        p_rientro = self._a_minuti(self.var[2].get())

        if None in (entrata, p_uscita, p_rientro):
            self.var[3].set("--:--")
            return

        pausa = (p_rientro - p_uscita) % (24 * 60)   # gestisce anche pause oltre mezzanotte
        pausa = max(pausa, PAUSA_MINIMA_MINUTI)      # la pausa conta almeno 30 minuti
        uscita = entrata + ORE_LAVORO_MINUTI + pausa
        self.var[3].set(self._a_testo(uscita))
        self._salva_stato()

    # ------------------------------------------------------------------ #
    # PERSISTENZA (JSON nella home utente)
    # ------------------------------------------------------------------ #
    def _carica_stato(self):
        try:
            with open(FILE_SALVATAGGIO, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _salva_stato(self):
        self._stato.update({
            "orari": [v.get() for v in self.var[:3]],
            "x": self.winfo_x(),
            "y": self.winfo_y(),
        })
        try:
            with open(FILE_SALVATAGGIO, "w", encoding="utf-8") as f:
                json.dump(self._stato, f)
        except OSError:
            pass  # se il disco non è scrivibile il widget continua a funzionare

    def _ripristina_valori(self):
        for var, valore in zip(self.var, self._stato.get("orari", [])):
            var.set(valore)

    # ------------------------------------------------------------------ #
    # TRASCINAMENTO, RIDUCI A ICONA, CHIUDI
    # ------------------------------------------------------------------ #
    def _inizio_trascinamento(self, evento):
        self._drag_x = evento.x_root - self.winfo_x()
        self._drag_y = evento.y_root - self.winfo_y()

    def _trascina(self, evento):
        self.geometry(f"+{evento.x_root - self._drag_x}+{evento.y_root - self._drag_y}")

    def _riduci(self):
        """Le finestre frameless non si possono iconizzare direttamente:
        riattiviamo per un attimo la cornice di sistema, iconizziamo,
        e al ripristino (<Map>) la togliamo di nuovo."""
        self._salva_stato()
        self.overrideredirect(False)
        self.iconify()

    def _su_ripristino(self, evento):
        if self.state() == "normal" and not self.overrideredirect():
            self.after(10, lambda: self.overrideredirect(True))

    def _chiudi(self):
        self._salva_stato()
        self.destroy()


if __name__ == "__main__":
    GegenwichteWidget().mainloop()
