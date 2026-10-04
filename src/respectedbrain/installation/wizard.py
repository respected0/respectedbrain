"""Existing native wizard UI backed by the same installation services as CLI."""
from __future__ import annotations
from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

from respectedbrain import __version__
from respectedbrain.bootstrap import application_roots, bootstrap
from respectedbrain.core.config import ConfigStore
from respectedbrain.installation.setup import setup


def run_action(mode, roots, vault, *, profile, desired, backend, package=None):
    if mode in ("install", "modify"):
        return setup(roots, vault, profile=profile, desired=desired, backend=backend, package=package)
    ctx = bootstrap(vault=vault, env={"RESPECTED_APP_DIR": str(roots.app_root), "RESPECTED_DATA_DIR": str(roots.data_root)})
    if mode in ("update", "uninstall"):
        from .deferred import defer_operation
        queued = defer_operation(ctx, mode=mode, package=package)
        if queued is not None:
            return queued
    if mode == "update":
        from respectedbrain.installation.update import update
        if package is None:
            raise ValueError("Güncelleme için doğrulanmış yeni paket seçilmeli")
        return update(ctx, package=package, backend=backend)
    if mode == "repair":
        from respectedbrain.installation.repair import repair
        return repair(ctx, backend=backend)
    if mode == "uninstall":
        from respectedbrain.installation.uninstall import uninstall
        return uninstall(ctx, backend=backend)
    raise ValueError("Bilinmeyen işlem modu")


class SetupWizard:
    def __init__(self, root: tk.Tk, *, roots=None, backend=None) -> None:
        self.root = root
        self.roots = roots or application_roots()
        if backend is None:
            from respectedbrain.integrations.backend import NativeBackend
            backend = NativeBackend(self.roots.data_root)
        self.backend = backend
        self.root.title(f"Respected Brain {__version__} — Kurulum & Bakım")
        self.root.geometry("680x640")
        self.root.resizable(False, False)
        self.root.configure(bg="#0d1117")
        self.vault_path_var = tk.StringVar(value=str(self.roots.default_vault))
        self.user_name_var = tk.StringVar(value=Path.home().name)
        self.companion_var = tk.StringVar(value="Companion")
        self.model_choice_var = tk.StringVar(value="auto")
        self.mode_var = tk.StringVar(value="install")
        config = ConfigStore(self.roots.data_root).read()
        desired = config["integrations"]
        self.desktop_shortcut_var = tk.BooleanVar(value=desired.get("shortcut", False))
        self.schedule_var = tk.BooleanVar(value=desired.get("schedule", False))
        self.global_rules_var = tk.BooleanVar(value=desired.get("global", False))
        self.mcp_server_var = tk.BooleanVar(value=desired.get("mcp", False))
        self.model_choice_var.set(config["preferences"].get("summary_provider", "auto"))
        identity = config.get("active_vault_id")
        if identity is not None:
            entry = config["vaults"][identity]
            self.vault_path_var.set(entry["path"])
            self.mode_var.set("modify")
            settings = entry.get("settings", {})
            self.user_name_var.set(settings.get("USER_NAME", Path.home().name))
            self.companion_var.set(settings.get("COMPANION", "Companion"))
        self._build_ui()
        self._on_mode_change()
        self._log(f"Program: {self.roots.app_root}")
        self._log(f"Ayarlar ve teknik veri: {self.roots.data_root}")

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#0d1117", foreground="#c9d1d9", font=("Segoe UI", 10))
        style.configure("Header.TLabel", background="#0d1117", foreground="#58a6ff", font=("Segoe UI", 15, "bold"))
        style.configure("SubHeader.TLabel", background="#0d1117", foreground="#8b949e", font=("Segoe UI", 9))
        style.configure("Card.TFrame", background="#161b22")
        style.configure("TRadiobutton", background="#161b22", foreground="#c9d1d9", font=("Segoe UI", 9))
        style.configure("TCheckbutton", background="#161b22", foreground="#c9d1d9", font=("Segoe UI", 9))

        # Header
        header_frame = tk.Frame(self.root, bg="#0d1117", padx=20, pady=12)
        header_frame.pack(fill="x")

        title = ttk.Label(header_frame, text=f"⚡ Respected Brain {__version__} Kurulum & Yönetim", style="Header.TLabel")
        title.pack(anchor="w")
        desc = ttk.Label(
            header_frame,
            text="Program ve kişisel not kasası ayrı konumlarda tutulur.",
            style="SubHeader.TLabel",
        )
        desc.pack(anchor="w", pady=(1, 0))

        # Body Container
        card = tk.Frame(self.root, bg="#161b22", padx=16, pady=12, highlightbackground="#30363d", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=20, pady=2)

        # Status box
        self.status_box = tk.Text(
            card,
            height=4,
            bg="#090d13",
            fg="#58a6ff",
            font=("Consolas", 8),
            relief="flat",
            padx=8,
            pady=6,
            highlightbackground="#30363d",
            highlightthickness=1,
        )
        self.status_box.pack(fill="x", pady=(0, 8))
        self.status_box.insert("end", "[*] Respected Brain altyapısı başlatılıyor...\n")
        self.status_box.configure(state="disabled")

        # 1. Operation Mode Frame
        mode_frame = tk.LabelFrame(card, text=" İşlem Modu ", bg="#161b22", fg="#58a6ff", font=("Segoe UI", 9, "bold"), padx=8, pady=4)
        mode_frame.pack(fill="x", pady=(0, 8))

        modes = [
            ("🔄 Güncelle (Update)", "update"),
            ("🛠️ Onar (Repair)", "repair"),
            ("⚙️ Değiştir (Modify)", "modify"),
            ("🚀 Temiz Kurulum", "install"),
            ("🗑️ Kaldır (Uninstall)", "uninstall"),
        ]
        for text, val in modes:
            r = tk.Radiobutton(
                mode_frame,
                text=text,
                value=val,
                variable=self.mode_var,
                command=self._on_mode_change,
                bg="#161b22",
                fg="#f0f6fc",
                selectcolor="#090d13",
                activebackground="#161b22",
                activeforeground="#58a6ff",
                font=("Segoe UI", 9),
            )
            r.pack(side="left", padx=4)

        # 2. Vault Path Frame
        path_frame = tk.Frame(card, bg="#161b22")
        path_frame.pack(fill="x", pady=(0, 8))

        vault_label = tk.Label(path_frame, text="Kasa (Vault) Yolu:", bg="#161b22", fg="#c9d1d9", font=("Segoe UI", 9, "bold"))
        vault_label.pack(side="left")

        self.path_entry = tk.Entry(
            path_frame,
            textvariable=self.vault_path_var,
            bg="#090d13",
            fg="#f0f6fc",
            font=("Segoe UI", 9),
            relief="flat",
            highlightbackground="#30363d",
            highlightthickness=1,
        )
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=2, padx=(8, 8))

        browse_btn = tk.Button(
            path_frame,
            text="Gözat...",
            command=self._browse_vault,
            bg="#21262d",
            fg="#c9d1d9",
            relief="flat",
            font=("Segoe UI", 8),
            padx=8,
        )
        browse_btn.pack(side="right")

        # 3. User & Companion Profile Frame
        self.profile_frame = tk.LabelFrame(card, text=" Kullanıcı & Companion Profili ", bg="#161b22", fg="#58a6ff", font=("Segoe UI", 9, "bold"), padx=8, pady=4)
        self.profile_frame.pack(fill="x", pady=(0, 8))

        u_label = tk.Label(self.profile_frame, text="Hitap Şekli / Adınız:", bg="#161b22", fg="#c9d1d9", font=("Segoe UI", 9))
        u_label.grid(row=0, column=0, sticky="w", pady=2)
        u_entry = tk.Entry(self.profile_frame, textvariable=self.user_name_var, bg="#090d13", fg="#f0f6fc", width=22, relief="flat", highlightbackground="#30363d", highlightthickness=1)
        u_entry.grid(row=0, column=1, sticky="w", padx=(6, 20), pady=2)

        c_label = tk.Label(self.profile_frame, text="Companion Adı:", bg="#161b22", fg="#c9d1d9", font=("Segoe UI", 9))
        c_label.grid(row=0, column=2, sticky="w", pady=2)
        c_entry = tk.Entry(self.profile_frame, textvariable=self.companion_var, bg="#090d13", fg="#f0f6fc", width=22, relief="flat", highlightbackground="#30363d", highlightthickness=1)
        c_entry.grid(row=0, column=3, sticky="w", padx=6, pady=2)

        # 4. AI Model & Fallback Priority Frame
        self.model_frame = tk.LabelFrame(card, text=" Birincil AI Model ve Router Tercihi ", bg="#161b22", fg="#58a6ff", font=("Segoe UI", 9, "bold"), padx=8, pady=4)
        self.model_frame.pack(fill="x", pady=(0, 8))

        models = [
            ("⚡ Akıllı Otomatik (Auto — Önerilen)", "auto"),
            ("🪐 Google Antigravity", "antigravity"),
            ("🧠 OpenAI Codex", "codex"),
            ("🎭 Anthropic Claude", "claude"),
            ("✨ Google Gemini", "gemini"),
        ]
        for text, val in models:
            r = tk.Radiobutton(
                self.model_frame,
                text=text,
                value=val,
                variable=self.model_choice_var,
                bg="#161b22",
                fg="#c9d1d9",
                selectcolor="#090d13",
                activebackground="#161b22",
                font=("Segoe UI", 9),
            )
            r.pack(anchor="w", pady=1)

        # 5. Tasks / Integrations Frame
        self.tasks_frame = tk.LabelFrame(card, text=" Sistem Entegrasyonları ve Otomasyon ", bg="#161b22", fg="#58a6ff", font=("Segoe UI", 9, "bold"), padx=8, pady=4)
        self.tasks_frame.pack(fill="x", pady=(0, 4))

        chk1 = tk.Checkbutton(self.tasks_frame, text="Masaüstüne Kontrol Paneli kısayolu ekle", variable=self.desktop_shortcut_var, bg="#161b22", fg="#c9d1d9", selectcolor="#090d13", activebackground="#161b22", font=("Segoe UI", 9))
        chk1.pack(anchor="w", pady=1)

        chk2 = tk.Checkbutton(self.tasks_frame, text="Her sabah 08:00'de otomatik sabah brifingi zamanla (Windows Görev Zamanlayıcı)", variable=self.schedule_var, bg="#161b22", fg="#c9d1d9", selectcolor="#090d13", activebackground="#161b22", font=("Segoe UI", 9))
        chk2.pack(anchor="w", pady=1)

        chk3 = tk.Checkbutton(self.tasks_frame, text="Global AI kurallarına (~/.gemini, ~/.claude vb.) bağla", variable=self.global_rules_var, bg="#161b22", fg="#c9d1d9", selectcolor="#090d13", activebackground="#161b22", font=("Segoe UI", 9))
        chk3.pack(anchor="w", pady=1)

        chk4 = tk.Checkbutton(self.tasks_frame, text="Dış editörler için MCP Sunucusunu kaydet (Claude Desktop, Cursor, Antigravity)", variable=self.mcp_server_var, bg="#161b22", fg="#c9d1d9", selectcolor="#090d13", activebackground="#161b22", font=("Segoe UI", 9))
        chk4.pack(anchor="w", pady=1)

        # Progress bar
        self.progress = ttk.Progressbar(card, mode="indeterminate")
        self.progress.pack(fill="x", pady=(8, 4))

        # Footer Actions
        footer = tk.Frame(self.root, bg="#0d1117", padx=20, pady=10)
        footer.pack(fill="x")

        self.btn_action = tk.Button(
            footer,
            text="🚀 Başlat",
            command=self._start_action_thread,
            bg="#238636",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=20,
            pady=6,
            cursor="hand2",
        )
        self.btn_action.pack(side="right")

    def _log(self, text):
        def show():
            self.status_box.configure(state="normal")
            self.status_box.insert("end", text + "\n")
            self.status_box.see("end")
            self.status_box.configure(state="disabled")
        self.root.after(0, show)

    def _browse_vault(self):
        chosen = filedialog.askdirectory(initialdir=str(self.roots.default_vault.parent), title="Not Kasasını Seçin")
        if chosen:
            self.vault_path_var.set(chosen)

    def _on_mode_change(self):
        titles = {"update": "Programı Güncelle", "repair": "Programı Onar", "modify": "Ayarları Kaydet", "uninstall": "Programı Kaldır", "install": "Kur"}
        self.btn_action.configure(text=titles[self.mode_var.get()])

    def _start_action_thread(self):
        mode = self.mode_var.get()
        vault = Path(self.vault_path_var.get().strip()).resolve()
        package = None
        if mode == "update":
            chosen = filedialog.askdirectory(title="Yeni Dağıtım Paketini Seçin")
            if not chosen:
                return
            package = Path(chosen)
        if mode == "uninstall" and not messagebox.askyesno("Programı Kaldır", "Program kaldırılacak. Notlar ve ayarlar korunacak. Devam edilsin mi?"):
            return
        profile = {"OS_NAME": vault.name, "USER_NAME": self.user_name_var.get().strip() or Path.home().name,
                   "USER_BIO": "", "COMPANION": self.companion_var.get().strip() or "Companion",
                   "summary_provider": self.model_choice_var.get()}
        desired = {"global": self.global_rules_var.get(), "mcp": self.mcp_server_var.get(),
                   "schedule": self.schedule_var.get(), "shortcut": self.desktop_shortcut_var.get()}
        self.btn_action.configure(state="disabled")
        self.progress.start(10)
        def work():
            try:
                result = run_action(mode, self.roots, vault, profile=profile, desired=desired, backend=self.backend, package=package)
                if result.pending:
                    self._log("Pencere kapanınca işlem uygulanacak. Sonuç ayarlar klasöründeki backups altında kaydedilecek.")
                    self.root.after(0, self.root.destroy)
                    return
                self._log("İşlem tamamlandı." if result.success else "İşlem başarısız: " + "; ".join(result.conflicts))
                self.root.after(0, lambda: self._finish(result.success))
            except Exception as error:
                self._log(str(error))
                self.root.after(0, lambda: self._finish(False))
        threading.Thread(target=work, daemon=True).start()

    def _finish(self, success):
        self.progress.stop()
        self.btn_action.configure(state="normal")
        if success:
            messagebox.showinfo("Tamamlandı", "İşlem tamamlandı. Not kasasının konumu korunuyor.")
        else:
            messagebox.showerror("İşlem Başarısız", "Ayrıntılar işlem günlüğünde; kullanıcı dosyaları korunuyor.")


def main(*, roots=None, backend=None) -> int:
    root = tk.Tk()
    SetupWizard(root, roots=roots, backend=backend)
    root.mainloop()
    return 0
