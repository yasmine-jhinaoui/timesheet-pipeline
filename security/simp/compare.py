# Compare deux resultats OpenSCAP (avant/apres) regle par regle
import sys, xml.etree.ElementTree as ET
NS = '{http://checklists.nist.gov/xccdf/1.2}'
def load(f):
    t = ET.parse(f)
    res = {rr.get('idref').replace('xccdf_org.ssgproject.content_rule_', ''): rr.find(NS + 'result').text
           for rr in t.iter(NS + 'rule-result')}
    return res, float(t.find('.//' + NS + 'score').text)
av, sav = load(sys.argv[1]); ap, sap = load(sys.argv[2])
c = lambda r, k: sum(1 for v in r.values() if v == k)
print(f"{'':16}{'AVANT':>8}{'APRES':>8}")
for k in ('pass', 'fail', 'notapplicable', 'notchecked'):
    print(f"{k:16}{c(av, k):>8}{c(ap, k):>8}")
print(f"{'score':16}{sav:>7.1f}%{sap:>7.1f}%")
for titre, test in (("Corrigees (fail -> pass)", lambda r: av[r] == 'fail' and ap.get(r) == 'pass'),
                    ("Encore en echec", lambda r: ap.get(r) == 'fail'),
                    ("Regressions (pass -> fail)", lambda r: av[r] == 'pass' and ap.get(r) == 'fail')):
    print(f"\n== {titre} ==")
    for r in sorted(av):
        if test(r): print("  ", r)
