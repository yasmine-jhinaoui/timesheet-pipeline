#!/usr/bin/env python3
# Threat Intelligence : croise les CVE trouvees par OWASP Dependency-Check
# avec le catalogue CISA KEV (CVE activement exploitees) et les scores EPSS (FIRST.org).
# Usage : ti-check.py <rapport-dependency-check.xml> <dossier-sortie> [fichier-exceptions]
import datetime, json, os, sys, urllib.request
import xml.etree.ElementTree as ET

KEV_URL = 'https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json'
EPSS_URL = 'https://api.first.org/data/v1/epss?cve='
EPSS_HIGH = 0.5


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'timesheet-pipeline-threat-intel'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def load_cves(path):
    vulns = {}
    for dep in ET.parse(path).getroot().iterfind('.//{*}dependency'):
        name = dep.findtext('{*}fileName') or '?'
        for v in dep.iterfind('.//{*}vulnerability'):
            cve = v.findtext('{*}name') or ''
            if not cve.startswith('CVE-'):
                continue
            score = v.find('.//{*}baseScore')
            e = vulns.setdefault(cve, {'deps': set(), 'cvss': 0.0})
            e['deps'].add(name)
            if score is not None and score.text:
                e['cvss'] = max(e['cvss'], float(score.text))
    return vulns


def load_exceptions(path):
    exc, today = {}, datetime.date.today()
    if path and os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3 and datetime.date.fromisoformat(parts[1]) >= today:
                exc[parts[0]] = parts[2] + ' (jusqu au ' + parts[1] + ')'
    return exc


def main():
    report, out = sys.argv[1], sys.argv[2]
    exc = load_exceptions(sys.argv[3] if len(sys.argv) > 3 else '')
    os.makedirs(out, exist_ok=True)
    vulns = load_cves(report)
    kev_data = fetch(KEV_URL)
    kev = {v['cveID']: v for v in kev_data['vulnerabilities']}
    cves = sorted(vulns)
    epss = {}
    for i in range(0, len(cves), 50):
        for d in fetch(EPSS_URL + ','.join(cves[i:i + 50])).get('data', []):
            epss[d['cve']] = float(d['epss'])

    byc = {}
    for c in cves:
        byc[c] = {'cve': c, 'kev': c in kev, 'epss': epss.get(c, 0.0), 'cvss': vulns[c]['cvss'],
                  'deps': sorted(vulns[c]['deps']),
                  'ransomware': kev[c]['knownRansomwareCampaignUse'] if c in kev else '',
                  'kev_name': kev[c]['vulnerabilityName'] if c in kev else ''}
    rows = [byc[o[2]] for o in sorted((not r['kev'], -r['epss'], r['cve']) for r in byc.values())]
    kev_rows = [r for r in rows if r['kev']]
    high = [r for r in rows if not r['kev'] and r['epss'] >= EPSS_HIGH]
    blocking = [r for r in kev_rows if r['cve'] not in exc]

    lines = ['=== Threat Intelligence (CISA KEV + EPSS) ===',
             f"Date : {datetime.datetime.now():%Y-%m-%d %H:%M}",
             f"Catalogue CISA KEV : version {kev_data['catalogVersion']}, {kev_data['count']} CVE activement exploitees",
             f"CVE trouvees par Dependency-Check : {len(cves)}",
             f"  - dans le catalogue KEV (activement exploitees) : {len(kev_rows)}",
             f"  - EPSS >= {EPSS_HIGH} (exploitation probable sous 30 jours) : {len(high)}",
             f"  - autres : {len(cves) - len(kev_rows) - len(high)}",
             '', '== CVE activement exploitees (CISA KEV) ==']
    for r in kev_rows:
        status = 'EXCEPTION : ' + exc[r['cve']] if r['cve'] in exc else 'BLOQUANT'
        lines.append(f"  {r['cve']}  EPSS={r['epss']:.3f}  CVSS={r['cvss']}  ransomware={r['ransomware']}  [{status}]")
        lines.append(f"      {r['kev_name']} -> {', '.join(r['deps'])}")
    lines += ['', "== Top 10 par probabilite d'exploitation (EPSS) =="]
    for o in sorted((-r['epss'], r['cve']) for r in rows)[:10]:
        r = byc[o[1]]
        lines.append(f"  {r['cve']}  EPSS={r['epss']:.3f}  CVSS={r['cvss']}  KEV={'oui' if r['kev'] else 'non'}  -> {', '.join(r['deps'])}")
    lines += ['', f"RESULTAT : {len(blocking)} CVE activement exploitee(s) sans exception -> "
              + ('deploiement refuse' if blocking else 'aucun blocage')]
    text = '\n'.join(lines)
    print(text)
    open(os.path.join(out, 'ti-report.txt'), 'w').write(text + '\n')
    json.dump(rows, open(os.path.join(out, 'ti-report.json'), 'w'), indent=2)
    sys.exit(1 if blocking else 0)


if __name__ == '__main__':
    main()
