"""Existing native wizard UI backed by the same installation services as CLI."""
from __future__ import annotations
import os
from pathlib import Path
import sys
import threading


def ensure_tcl_tk_environment() -> None:
    """Ensure TCL_LIBRARY and TK_LIBRARY point to valid tcl/tk resource directories."""
    if os.name != "nt":
        return
    prefixes = [
        getattr(sys, "_MEIPASS", None),
        getattr(sys, "base_prefix", None),
        sys.prefix,
        Path(sys.executable).parent if getattr(sys, "frozen", False) else None,
    ]
    tcl_candidates = ["tcl/tcl8.6", "lib/tcl8.6", "_tcl_data", "tcl8.6"]
    tk_candidates = ["tcl/tk8.6", "lib/tk8.6", "_tk_data", "tk8.6"]
    if "TCL_LIBRARY" not in os.environ:
        for prefix in prefixes:
            if not prefix:
                continue
            base = Path(prefix)
            for sub in tcl_candidates:
                candidate = base / sub
                if (candidate / "init.tcl").is_file():
                    os.environ["TCL_LIBRARY"] = candidate.resolve().as_posix()
                    break
            if "TCL_LIBRARY" in os.environ:
                break
    if "TK_LIBRARY" not in os.environ:
        for prefix in prefixes:
            if not prefix:
                continue
            base = Path(prefix)
            for sub in tk_candidates:
                candidate = base / sub
                if (candidate / "tk.tcl").is_file():
                    os.environ["TK_LIBRARY"] = candidate.resolve().as_posix()
                    break
            if "TK_LIBRARY" in os.environ:
                break


ensure_tcl_tk_environment()
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

from respectedbrain import __version__
from respectedbrain.bootstrap import application_roots, bootstrap
from respectedbrain.core.config import ConfigStore
from respectedbrain.installation.setup import setup


def run_action(mode, roots, vault, *, profile, desired, backend, package=None, require_provenance=None):
    if mode in ("install", "modify"):
        return setup(roots, vault, profile=profile, desired=desired, backend=backend, package=package, require_provenance=require_provenance)
    ctx = bootstrap(vault=vault, env={"RESPECTED_APP_DIR": str(roots.app_root), "RESPECTED_DATA_DIR": str(roots.data_root)})
    if mode in ("update", "uninstall"):
        from .deferred import defer_operation
        queued = defer_operation(ctx, mode=mode, package=package, purge_data=True, require_provenance=require_provenance)
        if queued is not None:
            return queued
    if mode == "update":
        from respectedbrain.installation.update import update
        if package is None:
            raise ValueError("Güncelleme için doğrulanmış yeni paket seçilmeli")
        return update(ctx, package=package, backend=backend, require_provenance=require_provenance)
    if mode == "repair":
        from respectedbrain.installation.repair import repair
        return repair(ctx, backend=backend, package=package, require_provenance=require_provenance)
    if mode == "uninstall":
        from respectedbrain.installation.uninstall import uninstall
        return uninstall(ctx, backend=backend)
    raise ValueError("Bilinmeyen işlem modu")


class SetupWizard:
    def __init__(self, root: tk.Tk, *, roots=None, backend=None, vault=None, package=None, profile=None, desired=None) -> None:
        ensure_tcl_tk_environment()
        self.root = root
        self.roots = roots or application_roots()
        if backend is None:
            from respectedbrain.integrations.backend import NativeBackend
            backend = NativeBackend(self.roots.data_root)
        self.backend = backend
        self.package = Path(package).resolve() if package is not None else None
        self.root.title(f"Respected Brain {__version__} — Kurulum & Bakım")
        self.root.geometry("680x720")
        self.root.resizable(False, False)
        self.root.configure(bg="#0d1117")
        self.vault_path_var = tk.StringVar(value=str(self.roots.default_vault))
        self.vault_name_var = tk.StringVar(value=self.roots.default_vault.name)
        self.user_name_var = tk.StringVar(value=Path.home().name)
        self.user_bio_var = tk.StringVar(value="")
        self.companion_var = tk.StringVar(value="Companion")
        self.model_choice_var = tk.StringVar(value="auto")
        self.mode_var = tk.StringVar(value="install")
        config = ConfigStore(self.roots.data_root).read()
        selections = {**config["integrations"], **(desired or {})}
        self.desktop_shortcut_var = tk.BooleanVar(value=selections.get("shortcut", False))
        self.schedule_var = tk.BooleanVar(value=selections.get("schedule", False))
        self.global_rules_var = tk.BooleanVar(value=selections.get("global", False))
        self.mcp_server_var = tk.BooleanVar(value=selections.get("mcp", False))
        self.model_choice_var.set(config["preferences"].get("summary_provider", "auto"))
        self.explicit_profile = dict(profile or {})
        self.profile = {}
        selected_vault = Path(vault).resolve() if vault is not None else None
        identity = (next((key for key, entry in config["vaults"].items()
                          if Path(entry["path"]).resolve() == selected_vault), None)
                    if selected_vault is not None else config.get("active_vault_id"))
        if identity is not None:
            entry = config["vaults"][identity]
            self.vault_path_var.set(entry["path"])
            self.mode_var.set("modify")
            self.profile.update(entry.get("settings", {}))
        if selected_vault is not None:
            self.vault_path_var.set(str(selected_vault))
        self.profile.update(self.explicit_profile)
        self.vault_name_var.set(self.profile.get("OS_NAME", Path(self.vault_path_var.get()).name))
        self.user_name_var.set(self.profile.get("USER_NAME", Path.home().name))
        self.user_bio_var.set(self.profile.get("USER_BIO", ""))
        self.companion_var.set(self.profile.get("COMPANION", "Companion"))
        if "summary_provider" in self.profile:
            self.model_choice_var.set(self.profile["summary_provider"])
        # Remember the inherited widget defaults so the action can tell an
        # intentional edit apart from a stale value left over from another vault.
        self.default_os_name = self.vault_name_var.get()
        self.default_user_bio = self.user_bio_var.get()
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

        # 3. Vault identity and user context
        identity_frame = tk.LabelFrame(card, text=" Kasa ve Kullanıcı Bağlamı ", bg="#161b22", fg="#58a6ff", font=("Segoe UI", 9, "bold"), padx=8, pady=4)
        identity_frame.pack(fill="x", pady=(0, 8))

        vault_name_label = tk.Label(identity_frame, text="Kasa Adı:", bg="#161b22", fg="#c9d1d9", font=("Segoe UI", 9))
        vault_name_label.grid(row=0, column=0, sticky="w", pady=2)
        vault_name_entry = tk.Entry(identity_frame, textvariable=self.vault_name_var, bg="#090d13", fg="#f0f6fc", width=30, relief="flat", highlightbackground="#30363d", highlightthickness=1)
        vault_name_entry.grid(row=0, column=1, sticky="w", padx=(6, 20), pady=2)

        bio_label = tk.Label(identity_frame, text="Ne Yapıyorsunuz?", bg="#161b22", fg="#c9d1d9", font=("Segoe UI", 9))
        bio_label.grid(row=1, column=0, sticky="w", pady=2)
        bio_entry = tk.Entry(identity_frame, textvariable=self.user_bio_var, bg="#090d13", fg="#f0f6fc", width=52, relief="flat", highlightbackground="#30363d", highlightthickness=1)
        bio_entry.grid(row=1, column=1, sticky="w", padx=6, pady=2)

        # 4. User & Companion Profile Frame
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
        package = self.package
        if mode in ("update", "repair") and package is None:
            chosen = filedialog.askdirectory(title="Yeni Dağıtım Paketini Seçin")
            if not chosen:
                return
            package = Path(chosen).resolve()
        if mode == "uninstall" and not messagebox.askyesno("Programı Kaldır", "Program ve kanıtlı teknik kayıtları kaldırılacak. Notlar ve bilinmeyen dosyalar korunacak. Devam edilsin mi?"):
            return
        config = ConfigStore(self.roots.data_root).read()
        settings = next((entry.get("settings", {}) for entry in config["vaults"].values()
                         if Path(entry["path"]).resolve() == vault), {})
        # Hidden continuity fields are re-resolved from the *currently selected*
        # vault so switching to a fresh or different vault never inherits the
        # previous active vault's profile. Explicit CLI values win, including
        # intentional empty strings that must not fall back to saved values.
        profile = {**settings, **self.explicit_profile}
        profile["USER_NAME"] = self.user_name_var.get().strip() or settings.get("USER_NAME") or Path.home().name
        profile["COMPANION"] = self.companion_var.get().strip() or settings.get("COMPANION") or "Companion"
        profile["summary_provider"] = self.model_choice_var.get()

        def hidden_value(key, widget_value, inherited_value, fallback):
            if key in self.explicit_profile:
                return self.explicit_profile[key]
            if widget_value != inherited_value:
                return widget_value
            if key in settings:
                return settings[key]
            return fallback

        profile["OS_NAME"] = hidden_value("OS_NAME", self.vault_name_var.get(), self.default_os_name, vault.name)
        profile["USER_BIO"] = hidden_value("USER_BIO", self.user_bio_var.get(), self.default_user_bio, "")
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


def main(*, roots=None, backend=None, vault=None, package=None, profile=None, desired=None) -> int:
    ensure_tcl_tk_environment()
    root = tk.Tk()
    SetupWizard(root, roots=roots, backend=backend, vault=vault, package=package, profile=profile, desired=desired)
    timeout = os.environ.get("RESPECTED_GUI_TIMEOUT")
    if timeout:
        try:
            root.after(int(float(timeout) * 1000), root.destroy)
        except ValueError:
            pass
    root.mainloop()
    return 0
