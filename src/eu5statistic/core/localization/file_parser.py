from pathlib import Path


class LocalizationFileParser:
    """
    Parses a Paradox localization .yml file into a {key: value} dictionary.

    Line format:
        l_english:
         KEY: "Value"
         KEY2: Value
    """

    def __init__(self, encoding: str = "utf-8-sig") -> None:
        self.encoding = encoding

    def parse(self, file_path: Path) -> dict[str, str]:
        """
        Localization file parsing method

        :param file_path: Localization file
        :return: Paradox localization dictionary {key: value}

        Note: does not handle escaped quotes inside values. Paradox localization
        typically uses \" or '' for escaping, which is rare in practice.
        """
        data = {}
        with open(file_path, encoding=self.encoding) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Split at the first colon
                if ":" not in line:
                    continue
                key, rest = line.split(":", 1)
                key = key.strip()

                # Searching for quotation marks in the rest
                if '"' in rest:
                    start = rest.find('"')
                    end = rest.find('"', start + 1)
                    if end != -1:
                        value = rest[start + 1 : end]
                    else:
                        value = rest[start + 1 :]
                else:
                    value = rest.strip()
                data[key] = value

        return data
