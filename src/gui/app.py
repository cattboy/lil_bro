"""GUI entry point — QApplication + theme + splash + main window orchestration.

Called from ``src/main.py`` when ``--terminal`` is *not* set. Owns the
application object lifecycle, wires the splash → startup orchestrator →
main window handoff, and dismisses both PyInstaller native splash and
the QSplashScreen once startup completes.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from src.gui import theme
from src.gui.startup import StartupOrchestrator
from src.gui.widgets.splash import make_splash, show_splash_error, update_splash
from src.gui.windows.main_window import MainWindow


def run() -> int:
    """Boot the GUI. Returns the QApplication exit code."""
    QApplication.setApplicationName("lil_bro")
    QApplication.setOrganizationName("lil_bro")
    app = QApplication.instance() or QApplication(sys.argv)

    theme.load_fonts()
    app.setStyleSheet(theme.build_stylesheet())

    splash = make_splash()
    splash.show()
    app.processEvents()

    from src.gui.settings import Settings
    settings = Settings()
    main = MainWindow(settings=settings)

    thread = QThread()
    orchestrator = StartupOrchestrator()
    orchestrator.moveToThread(thread)
    thread.started.connect(orchestrator.run)
    orchestrator.finished.connect(thread.quit)

    startup_lhm_holder: dict[str, object] = {"lhm": None}

    def _on_step(name: str, status: str) -> None:
        if status == "fail":
            show_splash_error(splash, f"{name}: failed (continuing)")
        else:
            update_splash(splash, f"{name}…")

    def _on_finished(startup_lhm) -> None:
        startup_lhm_holder["lhm"] = startup_lhm
        try:
            import pyi_splash  # type: ignore[import-not-found]
            pyi_splash.close()
        except Exception:
            pass

        splash.finish(main)
        main.show()

    def _on_about_to_quit() -> None:
        try:
            from src.pipeline.post_run_cleanup import post_run_cleanup
            post_run_cleanup(startup_lhm_holder["lhm"])
        except Exception:
            pass
        try:
            settings.save_geometry(main)
        except Exception:
            pass

    app.aboutToQuit.connect(_on_about_to_quit)
    orchestrator.init_step.connect(_on_step)
    orchestrator.finished.connect(_on_finished)
    thread.start()

    return app.exec()
