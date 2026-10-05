#!/bin/bash
# Experience de Fault Injection controlee :
# kube-monkey tue UN pod de l'application, une sonde mesure la disponibilite chaque seconde.
set -u
NS=timesheet
URL=${URL:-http://192.168.49.2:30089/timesheet-devops/actuator/health}
DURATION=${DURATION:-150}
OUT=${OUT:-chaos-reports}
mkdir -p "$OUT"
log() { echo "$1" | tee -a "$OUT/chaos.log"; }

BEFORE=$(kubectl -n $NS get pods -l app=timesheet-app -o jsonpath='{.items[*].metadata.name}')
log "Debut de l'experience : $(date +%H:%M:%S)"
log "Pods de l'application avant : $BEFORE"

# Sonde : une requete par seconde sur le service, comme un utilisateur
( for i in $(seq 1 "$DURATION"); do
    echo "$(date +%H:%M:%S) $(curl -s -o /dev/null -m 1 -w '%{http_code}' "$URL")"
    sleep 1
  done ) > "$OUT/probe.log" &
PROBE=$!
sleep 5

# Injection : on allume kube-monkey jusqu'a la premiere victime, puis on l'eteint
kubectl -n chaos scale deployment/kube-monkey --replicas=1 > /dev/null
KILLED=""
for i in $(seq 1 120); do
  for p in $BEFORE; do
    D=$(kubectl -n $NS get pod "$p" -o jsonpath='{.metadata.deletionTimestamp}' 2>/dev/null || echo supprime)
    [ -n "$D" ] && KILLED="$p"
  done
  [ -n "$KILLED" ] && break
  sleep 1
done
kubectl -n chaos logs deployment/kube-monkey > "$OUT/kube-monkey.log" 2>&1
kubectl -n chaos scale deployment/kube-monkey --replicas=0 > /dev/null
log "Victime de kube-monkey : ${KILLED:-aucune} (a $(date +%H:%M:%S))"

wait $PROBE
TOTAL=$(wc -l < "$OUT/probe.log")
KO=$(grep -vc " 200$" "$OUT/probe.log")
FIRST=$(grep -v " 200$" "$OUT/probe.log" | head -1 | cut -d' ' -f1)
LAST=$(grep -v " 200$" "$OUT/probe.log" | tail -1 | cut -d' ' -f1)
log "Pods de l'application apres : $(kubectl -n $NS get pods -l app=timesheet-app --no-headers | awk '{print $1" "$3}' | tr '\n' ' ')"
log "Requetes : $TOTAL | en echec : $KO | disponibilite : $(( (TOTAL - KO) * 100 / TOTAL )) %"
[ "$KO" -gt 0 ] && log "Coupure observee de $FIRST a $LAST (environ $KO secondes)"
[ -z "$KILLED" ] && exit 2
[ "$KO" -gt 0 ] && exit 1
exit 0
