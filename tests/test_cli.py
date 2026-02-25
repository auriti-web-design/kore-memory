"""
Kore — Test per il modulo CLI (kore_memory/cli.py)
Verifica il parsing degli argomenti e la gestione degli errori.

Pattern: mock di uvicorn.run per evitare l'avvio reale del server.
Ogni test isola il parsing degli argomenti tramite sys.argv.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest


# ── Helper ────────────────────────────────────────────────────────────────────

def _esegui_main(argv: list[str]) -> None:
    """
    Imposta sys.argv e invoca main() con uvicorn mockato.
    Solleva SystemExit se argparse fallisce (argomenti non validi).
    """
    from kore_memory.cli import main

    with patch.dict(sys.modules, {"uvicorn": MagicMock()}):
        with patch("sys.argv", ["kore"] + argv):
            main()


# ── Argomenti di default ──────────────────────────────────────────────────────


class TestArgomentiDefault:
    """Verifica che i valori di default siano applicati correttamente."""

    def test_host_default(self):
        """Senza --host il server deve partire su 127.0.0.1."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore"]):
                from kore_memory.cli import main
                main()

        # Recupera i kwargs passati a uvicorn.run
        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["host"] == "127.0.0.1"

    def test_port_default(self):
        """Senza --port il server deve partire sulla porta 8765."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore"]):
                from kore_memory.cli import main
                main()

        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["port"] == 8765

    def test_reload_default_disabilitato(self):
        """Senza --reload il flag reload deve essere False."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore"]):
                from kore_memory.cli import main
                main()

        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["reload"] is False

    def test_log_level_default(self):
        """Senza --log-level il livello di log deve essere 'warning'."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore"]):
                from kore_memory.cli import main
                main()

        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["log_level"] == "warning"

    def test_app_target_corretto(self):
        """Il primo argomento di uvicorn.run deve puntare a kore_memory.main:app."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore"]):
                from kore_memory.cli import main
                main()

        args, _ = mock_uvicorn.run.call_args
        assert args[0] == "kore_memory.main:app"


# ── Argomenti personalizzati ──────────────────────────────────────────────────


class TestArgomentiPersonalizzati:
    """Verifica che gli argomenti da CLI vengano passati correttamente a uvicorn."""

    def test_host_personalizzato(self):
        """--host 0.0.0.0 deve essere trasmesso a uvicorn."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore", "--host", "0.0.0.0"]):
                from kore_memory.cli import main
                main()

        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["host"] == "0.0.0.0"

    def test_port_personalizzata(self):
        """--port 9000 deve essere trasmesso come intero a uvicorn."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore", "--port", "9000"]):
                from kore_memory.cli import main
                main()

        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["port"] == 9000

    def test_port_e_tipo_intero(self):
        """Il valore di --port deve essere di tipo int, non str."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore", "--port", "4321"]):
                from kore_memory.cli import main
                main()

        _, kwargs = mock_uvicorn.run.call_args
        assert isinstance(kwargs["port"], int)

    def test_reload_abilitato(self):
        """--reload deve impostare il flag reload=True in uvicorn."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore", "--reload"]):
                from kore_memory.cli import main
                main()

        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["reload"] is True

    def test_host_port_reload_combinati(self):
        """Tutti gli argomenti combinati devono essere passati correttamente."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore", "--host", "192.168.1.1", "--port", "7777", "--reload"]):
                from kore_memory.cli import main
                main()

        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["host"] == "192.168.1.1"
        assert kwargs["port"] == 7777
        assert kwargs["reload"] is True

    def test_log_level_debug(self):
        """--log-level debug deve essere accettato e passato a uvicorn."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore", "--log-level", "debug"]):
                from kore_memory.cli import main
                main()

        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["log_level"] == "debug"

    def test_log_level_info(self):
        """--log-level info deve essere accettato e passato a uvicorn."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore", "--log-level", "info"]):
                from kore_memory.cli import main
                main()

        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["log_level"] == "info"

    def test_log_level_error(self):
        """--log-level error deve essere accettato e passato a uvicorn."""
        mock_uvicorn = MagicMock()
        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("sys.argv", ["kore", "--log-level", "error"]):
                from kore_memory.cli import main
                main()

        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["log_level"] == "error"


# ── Argomenti non validi ──────────────────────────────────────────────────────


class TestArgomentiNonValidi:
    """Verifica che argomenti errati vengano rifiutati da argparse."""

    def test_port_non_numerica_rifiutata(self):
        """--port con valore non numerico deve causare SystemExit."""
        with pytest.raises(SystemExit) as exc:
            with patch("sys.argv", ["kore", "--port", "abc"]):
                from kore_memory.cli import main
                with patch.dict(sys.modules, {"uvicorn": MagicMock()}):
                    main()
        # argparse esce con codice 2 per errori di validazione
        assert exc.value.code == 2

    def test_log_level_non_valido_rifiutato(self):
        """--log-level con valore non nelle scelte deve causare SystemExit."""
        with pytest.raises(SystemExit) as exc:
            with patch("sys.argv", ["kore", "--log-level", "verbose"]):
                from kore_memory.cli import main
                with patch.dict(sys.modules, {"uvicorn": MagicMock()}):
                    main()
        assert exc.value.code == 2

    def test_argomento_sconosciuto_rifiutato(self):
        """Un argomento non riconosciuto deve causare SystemExit."""
        with pytest.raises(SystemExit) as exc:
            with patch("sys.argv", ["kore", "--opzione-inesistente"]):
                from kore_memory.cli import main
                with patch.dict(sys.modules, {"uvicorn": MagicMock()}):
                    main()
        assert exc.value.code == 2


# ── Uvicorn non trovato (ImportError) ────────────────────────────────────────


class TestUvicornNonTrovato:
    """Verifica il comportamento quando uvicorn non è installato."""

    def test_import_error_causa_exit_1(self):
        """Se uvicorn non è trovato, main() deve uscire con codice 1."""
        # Rimuove uvicorn dal cache dei moduli e simula ImportError
        with patch.dict(sys.modules, {"uvicorn": None}):
            with patch("sys.argv", ["kore"]):
                from kore_memory.cli import main
                with pytest.raises(SystemExit) as exc:
                    main()
        assert exc.value.code == 1

    def test_import_error_stampa_messaggio_su_stderr(self, capsys):
        """Se uvicorn non è trovato, deve stampare un messaggio su stderr."""
        with patch.dict(sys.modules, {"uvicorn": None}):
            with patch("sys.argv", ["kore"]):
                from kore_memory.cli import main
                with pytest.raises(SystemExit):
                    main()

        # Verifica che il messaggio di errore sia su stderr
        catturato = capsys.readouterr()
        assert "uvicorn" in catturato.err.lower()

    def test_import_error_non_stampa_su_stdout(self, capsys):
        """Il messaggio di errore di uvicorn non deve apparire su stdout."""
        with patch.dict(sys.modules, {"uvicorn": None}):
            with patch("sys.argv", ["kore"]):
                from kore_memory.cli import main
                with pytest.raises(SystemExit):
                    main()

        catturato = capsys.readouterr()
        assert catturato.out == ""
