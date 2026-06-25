#!/usr/bin/env python3
"""
NACHA / ACH Bridge MCP — CSOAI Layer-0 legacy-bridge family.
Parse NACHA ACH files (US payments), map to modern, govern (NACHA rules / OFAC).
Sibling of cobol-bridge-mcp.
Tools: parse_nacha · validate_nacha · map_to_modern · govern_ach
"""
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import List, Dict, Any

mcp = FastMCP("NACHA Bridge", instructions="Bridge NACHA / ACH payment files to ONE OS — parse, validate, map, govern (NACHA rules / OFAC).")

# ── SIGIL: every governed action → one signed hash-chained hop (SIGIL_LOG unifies all layers) ──
import hashlib as _hl, time as _t, json as _j, os as _os
_SIGIL_LOG = _os.environ.get("SIGIL_LOG", _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "bridge_sigil.log"))
def _sigil(op, body):
    try:
        prev = ""
        if _os.path.exists(_SIGIL_LOG):
            with open(_SIGIL_LOG) as f:
                ls = f.readlines()
                if ls: prev = _j.loads(ls[-1]).get("digest", "")
        ts = int(_t.time()); dg = _hl.sha256(f"{op}|{ts}|{prev[:8]}|{body}".encode()).hexdigest()[:16]
        _os.makedirs(_os.path.dirname(_SIGIL_LOG), exist_ok=True)
        with open(_SIGIL_LOG, "a") as f: f.write(_j.dumps({"ts": ts, "op": op, "body": body, "prev_digest": prev, "digest": dg}) + "\n")
        return dg
    except Exception: return ""

REC = {"1": "File Header", "5": "Batch Header", "6": "Entry Detail", "7": "Addenda", "8": "Batch Control", "9": "File Control"}


class NACHAParsed(BaseModel):
    record_counts: Dict[str, int] = Field(default_factory=dict)
    batches: int = 0
    entries: int = 0
    sec_codes: List[str] = Field(default_factory=list)
    line_count: int = 0


class Validation(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class Governance(BaseModel):
    risk_flags: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    attestable: bool = True
    note: str = ""


def _lines(f: str):
    return [ln for ln in f.replace("\r\n", "\n").split("\n") if ln.strip()]


@mcp.tool()
def parse_nacha(file_text: str) -> NACHAParsed:
    """Parse a NACHA ACH file: record-type counts, batches, entries, SEC codes."""
    lines = _lines(file_text)
    counts: Dict[str, int] = {}
    sec: List[str] = []
    for ln in lines:
        t = ln[0] if ln else ""
        name = REC.get(t, "Unknown")
        counts[name] = counts.get(name, 0) + 1
        if t == "5" and len(ln) >= 53:  # batch header carries the SEC code ~ positions 51-53
            code = ln[50:53].strip()
            if code and code not in sec:
                sec.append(code)
    return NACHAParsed(record_counts=counts, batches=counts.get("Batch Header", 0),
                       entries=counts.get("Entry Detail", 0), sec_codes=sec, line_count=len(lines))


@mcp.tool()
def validate_nacha(file_text: str) -> Validation:
    """Validate ACH file structure (file header/control present; record line length ~94)."""
    lines = _lines(file_text)
    errors, warnings = [], []
    if not lines or lines[0][:1] != "1":
        errors.append("Missing File Header (record type 1)")
    if not any(ln[:1] == "9" for ln in lines):
        warnings.append("Missing File Control (record type 9)")
    if any(len(ln) not in (94,) for ln in lines):
        warnings.append("Some records are not 94 characters (NACHA fixed width)")
    return Validation(valid=not errors, errors=errors, warnings=warnings)


@mcp.tool()
def map_to_modern(file_text: str) -> Dict[str, Any]:
    """Map an ACH file to a modern payment-batch JSON summary for ONE OS."""
    p = parse_nacha(file_text)
    return {"source": "NACHA ACH", "batches": p.batches, "entries": p.entries,
            "sec_codes": p.sec_codes, "target": "modern payment batch"}


@mcp.tool()
def govern_ach(file_text: str) -> Governance:
    """Governance: ACH risk surface — SEC code, OFAC, same-day exposure (attestable for CSOAI)."""
    _sigil("G", "nacha|govern_ach")
    p = parse_nacha(file_text)
    flags = []
    if any(c in ("WEB", "TEL") for c in p.sec_codes):
        flags.append("WEB/TEL SEC code — heightened authorisation + fraud controls (NACHA)")
    flags.append("Screen originator + receiver against OFAC SDN before release")
    return Governance(risk_flags=flags,
                      frameworks=["NACHA Operating Rules", "OFAC sanctions", "Reg E (consumer)", "BSA/AML", "DORA"],
                      note="CSOAI governs the bridge: ACH batch lineage attestable on the ledger.")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
