"""Test de coherencia para el versionado de la plantilla (Contrato 14).

Fija que CHANGELOG.md, README.md (EN/ES) y knowledge/plantilla-upgrade.md
estén sincronizados por máquina.
"""

import unittest
import re
from pathlib import Path


class TestVersioning(unittest.TestCase):
    """Tests que aseguran la coherencia del versionado de la plantilla."""

    @classmethod
    def setUpClass(cls):
        """Prepara rutas base para los tests."""
        cls.repo_root = Path(__file__).parent.parent
        cls.changelog = cls.repo_root / "CHANGELOG.md"
        cls.readme = cls.repo_root / "README.md"
        cls.upgrade_node = cls.repo_root / "knowledge" / "plantilla-upgrade.md"
        cls.index_node = cls.repo_root / "knowledge" / "index.md"

    def test_changelog_first_entry_is_semver(self) -> None:
        """CHANGELOG.md existe y su primera entrada ## v matchea semver."""
        self.assertTrue(
            self.changelog.exists(),
            f"CHANGELOG.md falta en {self.changelog}"
        )

        content = self.changelog.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Busca la primera línea que comience con "## v"
        semver_line = None
        for line in lines:
            if line.startswith("## v"):
                semver_line = line
                break

        self.assertIsNotNone(
            semver_line,
            f"CHANGELOG.md existe pero no tiene una entrada '## v...' en {self.changelog}"
        )

        # Extrae la versión (ej: "## v1.0.0 — 2026-07-07" -> "v1.0.0")
        # Regex: ## v(\d+\.\d+\.\d+)
        match = re.search(r"##\s+v(\d+\.\d+\.\d+)", semver_line)
        self.assertIsNotNone(
            match,
            f"CHANGELOG.md tiene entrada '## v' pero no matchea semver pattern en línea: {semver_line}"
        )

    def test_readme_mentions_changelog_en_and_es(self) -> None:
        """README.md menciona CHANGELOG.md en EN y en ES."""
        self.assertTrue(
            self.readme.exists(),
            f"README.md falta en {self.readme}"
        )

        content = self.readme.read_text(encoding="utf-8")

        # Particiona por <a id="español">
        if "<a id=\"español\">" not in content:
            self.fail(
                "README.md no contiene el ancla '<a id=\"español\">' para particionar EN/ES"
            )

        english_section, spanish_section = content.split("<a id=\"español\">", 1)

        # Busca "CHANGELOG.md" en la sección EN
        self.assertIn(
            "CHANGELOG.md",
            english_section,
            "README.md sección EN (antes de <a id='español'>) no menciona CHANGELOG.md"
        )

        # Busca "CHANGELOG.md" en la sección ES
        self.assertIn(
            "CHANGELOG.md",
            spanish_section,
            "README.md sección ES (después de <a id='español'>) no menciona CHANGELOG.md"
        )

    def test_upgrade_node_exists_and_indexed(self) -> None:
        """knowledge/plantilla-upgrade.md existe y está enlazado desde index.md."""
        self.assertTrue(
            self.upgrade_node.exists(),
            f"knowledge/plantilla-upgrade.md falta en {self.upgrade_node}"
        )

        # Verifica que index.md existe
        self.assertTrue(
            self.index_node.exists(),
            f"knowledge/index.md falta en {self.index_node}"
        )

        index_content = self.index_node.read_text(encoding="utf-8")

        # Busca el enlace a plantilla-upgrade.md
        # Puede ser [Texto](./plantilla-upgrade.md) o similar variantes
        self.assertIn(
            "plantilla-upgrade.md",
            index_content,
            "knowledge/index.md no enlaza plantilla-upgrade.md"
        )


if __name__ == "__main__":
    unittest.main()
