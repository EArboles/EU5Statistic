import subprocess
from pathlib import Path


class BinaryToJsonConverter:
    """
    Converts an EU5 binary save file into JSON format
    """

    def __init__(self, rakaly_path: Path, encoding: str = "utf-8") -> None:
        """
        :param rakaly_path: Full path to the Rakaly executable file
        """
        self.rakaly_path = rakaly_path
        self.encoding = encoding
        self._check_rakaly()

    def _check_rakaly(self) -> None:
        """Checks whether rakaly exists and is accessible."""
        if not self.rakaly_path.is_file():
            raise FileNotFoundError(f"Rakaly not found at path: {self.rakaly_path}")

    def convert_to_json(self, save_path: Path, output_path: Path) -> None:
        """
        Converts a binary save file into a text format using `rakaly json`.

        :param save_path: Path to the save file (.eu5)
        :param output_path: Path where the JSON file should be saved.
        If not specified, the text is returned as a string.

        Note: subprocess.run is blocking. For a single-file pipeline this is
        acceptable; for parallel processing use asyncio.create_subprocess_exec.
        """
        if not save_path.is_file():
            raise FileNotFoundError(f"Save file not found: {save_path}")

        cmd = [
            str(self.rakaly_path),
            "json",
            "--pretty",
            "-k",
            "group",
            str(save_path),
            "-f",
            self.encoding,
        ]

        with open(output_path, "w", encoding=self.encoding) as f:
            result = subprocess.run(
                cmd,
                stdout=f,  # output is directed to a file
                stderr=subprocess.PIPE,  # errors can be captured separately
                text=True,  # work with strings (rather than bytes)
                check=False,  # do not raise an exception on error
                timeout=120,  # seconds
            )

        if result.returncode != 0:
            raise RuntimeError(f"Rakaly finished with code {result.returncode}: {result.stderr}")
