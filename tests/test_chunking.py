from legacylens.chunking.cobol import chunk_cobol_file


def test_detects_paragraph_only_inside_procedure_division() -> None:
    source = """IDENTIFICATION DIVISION.
PROGRAM-ID. SAMPLE.
DATA DIVISION.
WORKING-STORAGE SECTION.
VALUE-ONE.
PROCEDURE DIVISION.
MAIN-SECTION.
    PERFORM READ-FILE.
READ-FILE.
    OPEN INPUT MYFILE.
    READ MYFILE AT END DISPLAY 'DONE'.
    STOP RUN.
"""
    chunks = chunk_cobol_file("sample.cob", source)

    assert chunks
    assert all(chunk.division == "PROCEDURE DIVISION" for chunk in chunks)
    assert any(chunk.symbol_name == "READ-FILE" for chunk in chunks)
    assert all(chunk.symbol_name != "PROCEDURE DIVISION" for chunk in chunks)
    assert any("io" in chunk.tags for chunk in chunks)


def test_uses_fallback_when_no_paragraphs() -> None:
    source = "\n".join(["IDENTIFICATION DIVISION.", "PROGRAM-ID. X."] + ["MOVE A TO B"] * 120)
    chunks = chunk_cobol_file("fallback.cob", source)

    assert chunks
    assert all(chunk.symbol_type == "fallback" for chunk in chunks)
