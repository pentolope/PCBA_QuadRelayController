from __future__ import annotations

import hashlib
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(REPO_ROOT, "evidence", "index.json")
DATASHEET_DIR = os.path.join(REPO_ROOT, "evidence", "datasheets")

#: Every document a claim in this repository rests on. `url` is where the file
#: came from; `document_id` is the revision the file itself states, which is
#: what a later reader has to match to know they are reading the same thing.
SOURCES = {
    "g2rl_omron": {
        "file": "datasheets/g2rl_omron.pdf",
        "url": "https://www.lcsc.com/datasheet/"
               "lcsc_datasheet_2211282130_Omron-Electronics-G2RL-1-E-DC5_"
               "C1524515.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Omron G2RL PCB Power Relay datasheet",
        "applies_to": ["G2RL-1-E DC5"],
    },
    "py32f003_puya": {
        "file": "datasheets/py32f003_puya.pdf",
        "url": "https://download.py32.org/Datasheet/en/"
               "PY32F003_Datasheet_Rev1.7.pdf",
        "retrieved": "2026-09-01",
        "document_id": "PY32F003 Datasheet Rev1.7",
        "applies_to": ["PY32F003F18P6TU"],
    },
    "tpd1e10b06_ti": {
        "file": "datasheets/tpd1e10b06_ti.pdf",
        "url": "https://www.ti.com/lit/ds/symlink/tpd1e10b06.pdf",
        "retrieved": "2026-09-01",
        "document_id": "SLLSEB1G, revised August 2024",
        "applies_to": ["TPD1E10B06DPYR"],
    },
    "ao3400a_aos": {
        "file": "datasheets/ao3400a_aos.pdf",
        "url": "https://www.lcsc.com/datasheet/"
               "lcsc_datasheet_1811081213_Alpha---Omega-Semicon-AO3400A_"
               "C20917.pdf",
        "retrieved": "2026-09-02",
        "document_id": "AO3400A Rev 3, December 2011",
        "applies_to": ["AO3400A"],
    },
    "ao3401a_aos": {
        "file": "datasheets/ao3401a_aos.pdf",
        "url": "https://www.lcsc.com/datasheet/"
               "lcsc_datasheet_2412061733_Alpha---Omega-Semicon-AO3401A_"
               "C15127.pdf",
        "retrieved": "2026-09-02",
        "document_id": "AO3401A Rev 3.1, December 2023",
        "applies_to": ["AO3401A"],
    },
    "1n4148w_semtech": {
        "file": "datasheets/1n4148w_st.pdf",
        "url": "https://www.lcsc.com/datasheet/"
               "lcsc_datasheet_1811061725_ST-Semtech-1N4148W_C81598.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Semtech Electronics 1N4148W, Rev 05, 20/09/2016",
        "applies_to": ["1N4148W"],
    },
    "kt0603r_kento": {
        "file": "datasheets/kt0603r_kento.pdf",
        "url": "https://www.lcsc.com/datasheet/"
               "lcsc_datasheet_1810231112_Hubei-KENTO-Elec-KT-0603R_"
               "C2286.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Hubei KENTO KT-0603R specification, Rev A.0, "
                       "2018-12-06",
        "applies_to": ["KT-0603R"],
    },
    "hb9500m_kangnex": {
        "file": "datasheets/hb9500m_kangnex.pdf",
        "url": "https://www.lcsc.com/datasheet/"
               "lcsc_datasheet_1912251712_Ningbo-Kangnex-Elec-HB9500M-9-5-3P_"
               "C162697.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Ningbo Kangnex HB9500M series drawing, pitch 9.50 mm",
        "applies_to": ["HB9500M-9.5-03P-13-00A"],
    },
    "kf128_cixikefa": {
        "file": "datasheets/kf128_cixikefa.pdf",
        "url": "https://www.lcsc.com/datasheet/"
               "lcsc_datasheet_2408211511_Cixi-Kefa-Elec-KF128-5-08-2P-AA_"
               "C474952.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Cixi Kefa KF128-5.08 drawing rev A, 2021-03-13",
        "applies_to": ["KF128-5.08-2P-AA"],
    },
    "header1x5_kinghelm": {
        "file": "datasheets/header1x5_kinghelm.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2201121530_Shenzhen-Kinghelm-Elec-KH-2-54PH180-1X5P-L11-5_"
               "C2932699.pdf",
        "retrieved": "2026-09-02",
        "applies_to": ["KH-2.54PH180-1X5P-L11.5"],
    },
    "header1x4_kinghelm": {
        "file": "datasheets/header1x4_kinghelm.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2110191530_Shenzhen-Kinghelm-Elec-KH-2-54PH180-1X4P-L11-5_"
               "C2905435.pdf",
        "retrieved": "2026-09-02",
        "applies_to": ["KH-2.54PH180-1X4P-L11.5"],
    },
    "res_0603_uniroyal": {
        "file": "datasheets/res_0603_uniroyal.pdf",
        "url": "https://www.lcsc.com/datasheet/"
               "lcsc_datasheet_2411221126_UNI-ROYAL-Uniroyal-Elec-"
               "0603WAF1000T5E_C22775.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Uniroyal chip resistor series specification",
        "applies_to": ["0603WAF1000T5E", "0603WAF2201T5E", "0603WAF1501T5E",
                       "0603WAF1002T5E", "0603WAF1003T5E", "0603WAF470KT5E"],
    },
    "mlcc_100nf_yageo": {
        "file": "datasheets/mlcc_100nf_yageo.pdf",
        "url": "https://www.lcsc.com/datasheet/"
               "lcsc_datasheet_2211101700_YAGEO-CC0603KRX7R9BB104_C14663.pdf",
        "retrieved": "2026-09-02",
        "applies_to": ["CC0603KRX7R9BB104"],
    },
    "mlcc_10uf_samsung": {
        "file": "datasheets/mlcc_10uf_samsung.pdf",
        "url": "https://www.lcsc.com/datasheet/"
               "lcsc_datasheet_2304140030_Samsung-Electro-Mechanics-"
               "CL21A106KAYNNNE_C15850.pdf",
        "retrieved": "2026-09-02",
        "applies_to": ["CL21A106KAYNNNE"],
    },
    "clearance_creepage_ti_slup421": {
        "file": "datasheets/clearance_creepage_ti_slup421.pdf",
        "url": "https://www.ti.com/lit/pdf/SLUP421",
        "retrieved": "2026-09-02",
        "document_id": "SLUP421, Demystifying Clearance and Creepage Distance "
                       "for High-Voltage End Equipment",
        "applies_to": ["IEC 60664-1 tables F.1, F.2, F.4"],
    },
    "clearance_creepage_ti_slup419": {
        "file": "datasheets/clearance_creepage_ti_slup419.pdf",
        "url": "https://www.ti.com/lit/pdf/slup419",
        "retrieved": "2026-09-02",
        "document_id": "SLUP419, March 2024",
        "applies_to": ["IEC 60664-1 tables F.1, F.2, F.4"],
    },
}


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_index():
    entries = {}
    for name in sorted(SOURCES):
        source = SOURCES[name]
        path = os.path.join(REPO_ROOT, "evidence", source["file"])
        entry = dict(source)
        entry["sha256"] = digest(path)
        entry["bytes"] = os.path.getsize(path)
        entries[name] = entry
    return {"schema_version": 1, "documents": entries}


def load_index():
    with open(INDEX_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_index():
    with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(compute_index(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return INDEX_PATH


def verify():
    """Every recorded document present and unchanged, and nothing unrecorded."""
    recorded = load_index()["documents"]
    present = {name for name in os.listdir(DATASHEET_DIR)
               if name.endswith((".pdf", ".json"))}
    referenced = {os.path.basename(entry["file"])
                  for entry in recorded.values()}
    problems = []
    for name in sorted(referenced - present):
        problems.append(("missing_file", name))
    for name in sorted(present - referenced):
        problems.append(("unreferenced_file", name))
    for name in sorted(recorded):
        entry = recorded[name]
        path = os.path.join(REPO_ROOT, "evidence", entry["file"])
        if not os.path.isfile(path):
            continue
        if digest(path) != entry["sha256"]:
            problems.append(("digest_mismatch", name))
    return problems


if __name__ == "__main__":
    sys.stdout.write(write_index() + "\n")
