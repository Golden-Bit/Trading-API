import os


def merge_documents(input_dir, output_file):
    # Legge tutti i file (documenti) presenti nella directory di input
    files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]

    with open(output_file, "w", encoding="utf-8") as outfile:
        for filename in files:
            file_path = os.path.join(input_dir, filename)
            with open(file_path, "r", encoding="utf-8") as infile:
                content = infile.read()
            content_length = len(content)

            separator = "#" * 40  # Linea di separazione
            # Scrive il blocco separatore con nome file e lunghezza
            outfile.write(separator + "\n")
            outfile.write(f"{filename} - lunghezza: {content_length}\n")
            outfile.write(separator + "\n")
            # Scrive il contenuto del file
            outfile.write(content + "\n")


if __name__ == "__main__":
    input_dir = "docs_pt3"  # Path di input contenente i documenti
    output_file = "merged_docs_pt3.txt"  # File di output in cui unire i documenti
    merge_documents(input_dir, output_file)
