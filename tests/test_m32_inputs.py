from __future__ import annotations

import builtins
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flycall_data import m32_inputs
from flycall_data.m32_inputs import M32GraphPaths, M32InputGateError


def _write_valid_artifacts(root: Path) -> tuple[M32GraphPaths, dict[str, str]]:
    graph_dir = root / "graph"
    graph_dir.mkdir(parents=True)
    io_dir = root / "io"
    io_dir.mkdir(parents=True)
    nodes_path = graph_dir / "nodes.parquet"
    edges_path = graph_dir / "edges.parquet"
    nodes_path.write_bytes(b"node parquet sentinel")
    edges_path.write_bytes(b"edge parquet sentinel")
    nodes_sha256 = hashlib.sha256(nodes_path.read_bytes()).hexdigest()
    edges_sha256 = hashlib.sha256(edges_path.read_bytes()).hexdigest()
    graph_manifest = {
        "outputs": {
            "nodes": {"path": "nodes.parquet", "sha256": nodes_sha256},
            "edges": {"path": "edges.parquet", "sha256": edges_sha256},
        }
    }
    graph_manifest_path = graph_dir / "manifest.json"
    graph_manifest_path.write_text(json.dumps(graph_manifest, indent=2) + "\n", encoding="utf-8")
    graph_manifest_sha256 = m32_inputs._sha256_manifest(graph_manifest_path)
    io_manifest = {
        "source_graph": {
            "manifest_sha256": graph_manifest_sha256,
            "nodes": {"sha256": nodes_sha256},
            "edges": {"sha256": edges_sha256},
        }
    }
    io_manifest_path = io_dir / "io_manifest.json"
    io_manifest_path.write_text(json.dumps(io_manifest, indent=2) + "\n", encoding="utf-8")
    paths = M32GraphPaths(graph_dir=graph_dir, io_manifest_path=io_manifest_path)
    hashes = {
        "graph_manifest": graph_manifest_sha256,
        "io_manifest": m32_inputs._sha256_manifest(io_manifest_path),
        "nodes": nodes_sha256,
        "edges": edges_sha256,
    }
    return paths, hashes


class M32GraphProvenanceTests(unittest.TestCase):
    def test_git_crlf_checkout_keeps_the_pinned_manifest_content_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths, expected = _write_valid_artifacts(Path(directory))
            for manifest_path in (paths.graph_manifest_path, paths.io_manifest_path):
                content = manifest_path.read_bytes().replace(b"\r\n", b"\n")
                manifest_path.write_bytes(content.replace(b"\n", b"\r\n"))
            with (
                patch.object(m32_inputs, "PINNED_M12_MANIFEST_SHA256", expected["graph_manifest"]),
                patch.object(m32_inputs, "PINNED_M13_IO_MANIFEST_SHA256", expected["io_manifest"]),
            ):
                result = m32_inputs.verify_m32_graph_provenance(paths)
            self.assertEqual(result["graph_manifest_sha256"], expected["graph_manifest"])
            self.assertEqual(result["io_manifest_sha256"], expected["io_manifest"])
            self.assertEqual(result["nodes_sha256"], expected["nodes"])
            self.assertEqual(result["edges_sha256"], expected["edges"])

    def test_pin_mismatch_fails_before_any_parquet_reader_import(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths, _hashes = _write_valid_artifacts(Path(directory))
            observed_imports: list[str] = []
            real_import = builtins.__import__

            def import_guard(name: str, *args: object, **kwargs: object) -> object:
                if name == "pyarrow" or name.startswith("pyarrow."):
                    observed_imports.append(name)
                return real_import(name, *args, **kwargs)

            with (
                patch.object(m32_inputs, "PINNED_M12_MANIFEST_SHA256", "0" * 64),
                patch.object(m32_inputs, "PINNED_M13_IO_MANIFEST_SHA256", "1" * 64),
                patch("builtins.__import__", side_effect=import_guard),
            ):
                with self.assertRaisesRegex(M32InputGateError, "Parquet files have not been opened"):
                    m32_inputs.verify_m32_graph_provenance(paths)
            self.assertEqual(observed_imports, [])

    def test_matching_manifest_and_raw_artifact_hashes_pass_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths, hashes = _write_valid_artifacts(Path(directory))
            with (
                patch.object(m32_inputs, "PINNED_M12_MANIFEST_SHA256", hashes["graph_manifest"]),
                patch.object(m32_inputs, "PINNED_M13_IO_MANIFEST_SHA256", hashes["io_manifest"]),
            ):
                result = m32_inputs.verify_m32_graph_provenance(paths)
            self.assertEqual(result["nodes_sha256"], hashes["nodes"])
            self.assertEqual(result["edges_sha256"], hashes["edges"])

    def test_parquet_runtime_denial_is_reported_before_rows_are_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths, hashes = _write_valid_artifacts(Path(directory))
            real_import = builtins.__import__

            def deny_pyarrow(name: str, *args: object, **kwargs: object) -> object:
                if name == "pyarrow" or name.startswith("pyarrow."):
                    raise PermissionError("simulated Windows Application Control denial")
                return real_import(name, *args, **kwargs)

            with (
                patch.object(m32_inputs, "PINNED_M12_MANIFEST_SHA256", hashes["graph_manifest"]),
                patch.object(m32_inputs, "PINNED_M13_IO_MANIFEST_SHA256", hashes["io_manifest"]),
                patch("builtins.__import__", side_effect=deny_pyarrow),
            ):
                with self.assertRaisesRegex(M32InputGateError, "graph rows were not read"):
                    m32_inputs.load_m32_graph(paths)


if __name__ == "__main__":
    unittest.main()
