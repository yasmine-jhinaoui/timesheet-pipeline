#!/usr/bin/env python3
"""Lit les rapports de securite du build et envoie les chiffres cles a la Pushgateway."""
import glob, json, os, re, sys, time, urllib.request
import xml.etree.ElementTree as ET

PUSHGATEWAY = os.environ.get("PUSHGATEWAY_URL", "http://localhost:9091")
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
PORTS_AUTORISES = {"30089", "30081"}
XCCDF = "{http://checklists.nist.gov/xccdf/1.2}"
metriques = []

def ajouter(nom, valeur, aide, labels=None):
    lab = "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}" if labels else ""
    metriques.append((nom, aide, f"{nom}{lab} {valeur}"))
    print(f"  {nom}{lab} = {valeur}")

def trouver(*chemins):
    for c in chemins:
        r = glob.glob(c)
        if r:
            return r[0]
    return None

def local(tag):
    return tag.rsplit("}", 1)[-1]

build = sys.argv[1] if len(sys.argv) > 1 else "0"
print("== Dependency-Check + Threat Intelligence")
f = trouver("target/dependency-check-report.xml")
if f:
    cves, sev = set(), {}
    for v in ET.parse(f).iter():
        if local(v.tag) != "vulnerability":
            continue
        nom = niveau = None
        for c in v:
            if local(c.tag) == "name":
                nom = (c.text or "").strip()
            elif local(c.tag) == "severity":
                niveau = (c.text or "").strip().upper().replace("MODERATE", "MEDIUM")
        if nom and nom not in cves:
            cves.add(nom)
            sev[niveau or "UNKNOWN"] = sev.get(niveau or "UNKNOWN", 0) + 1
    ajouter("devsecops_cve_total", len(cves), "Vulnerabilites uniques trouvees par Dependency-Check")
    for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        ajouter("devsecops_cve_par_severite", sev.get(s, 0), "CVE par severite", {"severite": s.lower()})
    try:
        kev = json.load(urllib.request.urlopen(KEV_URL, timeout=30))
        ids = {x["cveID"] for x in kev["vulnerabilities"]}
        ajouter("devsecops_cve_kev", len(cves & ids), "CVE presentes dans le catalogue CISA KEV")
    except Exception as e:
        print("  catalogue KEV indisponible :", e)
else:
    print("  rapport absent")

print("== ZAP")
f = trouver("zap-reports/zap-report.json", "zap-report.json")
if f:
    niveaux = {"3": "elevee", "2": "moyenne", "1": "faible", "0": "info"}
    compte = dict.fromkeys(niveaux.values(), 0)
    for site in json.load(open(f)).get("site", []):
        for a in site.get("alerts", []):
            n = niveaux.get(str(a.get("riskcode")))
            if n:
                compte[n] += 1
    for n, v in compte.items():
        ajouter("devsecops_zap_alertes", v, "Alertes ZAP par niveau de risque", {"risque": n})
else:
    print("  rapport absent")

print("== nmap")
f = trouver("zap-reports/nmap-report.txt", "nmap-report.txt")
if f:
    ports = set(re.findall(r"^(\d+)/tcp\s+open", open(f).read(), re.M))
    ajouter("devsecops_ports_ouverts", len(ports), "Ports ouverts sur le cluster")
    ajouter("devsecops_ports_inattendus", len(ports - PORTS_AUTORISES), "Ports ouverts non autorises")
else:
    print("  rapport absent")

print("== OSQuery")
f = trouver("osquery-reports/summary.txt", "summary.txt")
if f:
    regles = [l for l in open(f) if re.match(r"\s*R[eè]gle \d", l)]
    ok = sum(1 for l in open(f) if re.match(r"\s+OK\b", l))
    ajouter("devsecops_osquery_regles_ok", ok, "Regles OSQuery respectees")
    ajouter("devsecops_osquery_regles_total", len(regles), "Regles OSQuery verifiees")
else:
    print("  rapport absent")

print("== fail2ban")
f = trouver("fail2ban-reports/jail-status.txt", "jail-status.txt")
if f:
    t = open(f).read()
    for cle, nom, aide in [("Currently banned", "devsecops_fail2ban_ip_bannies", "IP actuellement bannies"),
                           ("Total banned", "devsecops_fail2ban_bans_total", "Bannissements depuis le demarrage"),
                           ("Total failed", "devsecops_fail2ban_echecs_total", "Echecs de connexion detectes")]:
        m = re.search(cle + r":\s*(\d+)", t)
        if m:
            ajouter(nom, m.group(1), aide)
else:
    print("  rapport absent")

print("== SIMP + OpenSCAP")
for chemin, moment in [("simp-reports/avant-results.xml", "avant"), ("simp-reports/apres-results.xml", "apres")]:
    if not os.path.exists(chemin):
        print("  absent :", chemin)
        continue
    arbre = ET.parse(chemin)
    res = [r.find(XCCDF + "result").text for r in arbre.iter(XCCDF + "rule-result")]
    ok, ko = res.count("pass"), res.count("fail")
    score = next((s.text for s in arbre.iter(XCCDF + "score")), None)
    if score is None and ok + ko:
        score = round(100 * ok / (ok + ko), 1)
    if score is not None:
        ajouter("devsecops_stig_score", round(float(score), 1), "Score de conformite STIG en %", {"moment": moment})
    if moment == "apres":
        ajouter("devsecops_stig_regles", ok, "Regles STIG", {"etat": "ok"})
        ajouter("devsecops_stig_regles", ko, "Regles STIG", {"etat": "ko"})

ajouter("devsecops_build_numero", build, "Numero du build mesure")
ajouter("devsecops_mesure_timestamp", int(time.time()), "Heure de la mesure")

corps, vus = "", set()
for nom, aide, ligne in metriques:
    if nom not in vus:
        corps += f"# HELP {nom} {aide}\n# TYPE {nom} gauge\n"
        vus.add(nom)
    corps += ligne + "\n"
try:
    req = urllib.request.Request(f"{PUSHGATEWAY}/metrics/job/devsecops", data=corps.encode(), method="PUT")
    urllib.request.urlopen(req, timeout=10)
    print(f"== {len(metriques)} valeurs envoyees a la Pushgateway")
except Exception as e:
    print("== ATTENTION : envoi a la Pushgateway impossible :", e)
