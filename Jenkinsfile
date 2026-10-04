pipeline {
    agent any

    tools {
        maven 'M3'
    }

    environment {
        DOCKER_IMAGE = 'yasminejhinaoui/timesheet-devops'
        IMAGE_TAG    = "${BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Clean') {
            steps {
                sh 'mvn -B -ntp clean'
            }
        }

        stage('Compile') {
            steps {
                sh 'mvn -B -ntp compile'
            }
        }

        stage('Test') {
            steps {
                sh 'mvn -B -ntp test'
            }
            post {
                always {
                    junit 'target/surefire-reports/*.xml'
                }
            }
        }

        stage('OWASP Dependency-Check') {
            steps {
                withCredentials([string(credentialsId: 'nvd-api-key', variable: 'NVD_API_KEY')]) {
                    sh '''
                        mvn -B -ntp org.owasp:dependency-check-maven:12.1.0:check \
                            -DnvdApiKey=$NVD_API_KEY \
                            -Dformats=HTML,XML \
                            -DossindexAnalyzerEnabled=false \
                            -DretireJsAnalyzerEnabled=false \
                            -DnvdValidForHours=24 \
                            -DfailBuildOnCVSS=11
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'target/dependency-check-report.*', allowEmptyArchive: true
                }
            }
        }

        stage('SonarQube') {
            steps {
                withSonarQubeEnv('sonarqube') {
                    sh 'mvn -B -ntp org.sonarsource.scanner.maven:sonar-maven-plugin:4.0.0.4121:sonar -Dsonar.projectKey=timesheet-pipeline -Dsonar.projectName=timesheet-pipeline'
                }
            }
        }

        stage('Package') {
            steps {
                sh 'mvn -B -ntp package -DskipTests'
            }
            post {
                success {
                    archiveArtifacts artifacts: 'target/*.jar', fingerprint: true
                }
            }
        }

        stage('Deploy to Nexus') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'nexus-creds',
                                                  usernameVariable: 'NEXUS_USER',
                                                  passwordVariable: 'NEXUS_PASS')]) {
                    sh 'mvn -B -ntp -s ci-settings.xml deploy -DskipTests'
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh 'docker build -t $DOCKER_IMAGE:$IMAGE_TAG -t $DOCKER_IMAGE:latest .'
            }
        }

        stage('Docker Push') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DH_USER',
                                                  passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker push $DOCKER_IMAGE:$IMAGE_TAG
                        docker push $DOCKER_IMAGE:latest
                    '''
                }
            }
            post {
                always {
                    sh 'docker logout'
                }
            }
        }

        stage('Integration Test (Docker Compose + Docker Secrets)') {
            steps {
                withVault(configuration: [vaultUrl: 'http://127.0.0.1:8200', vaultCredentialId: 'vault-approle', engineVersion: 2], vaultSecrets: [[path: 'secret/timesheet/mysql', engineVersion: 2, secretValues: [[envVar: 'MYSQL_ROOT_PASSWORD', vaultKey: 'root_password']]]]) {
                    sh '''
                        rm -rf .secrets
                        mkdir -m 700 .secrets
                        printf '%s' "$MYSQL_ROOT_PASSWORD" > .secrets/mysql_root_password
                        chmod 644 .secrets/mysql_root_password
                        test -s .secrets/mysql_root_password || { echo "ERREUR : secret vide"; exit 1; }

                        docker compose -p timesheet-pipeline up -d

                        {
                            echo "=== Docker Secrets : verification ==="
                            date
                            for c in timesheet-mysql timesheet-app; do
                                echo ""
                                echo "--- $c : variables d'environnement visibles avec docker inspect"
                                docker inspect "$c" --format '{{range .Config.Env}}{{println .}}{{end}}'
                                echo "--- $c : secrets montes dans /run/secrets/"
                                docker inspect "$c" --format '{{range .Mounts}}{{println .Destination}}{{end}}' | grep /run/secrets
                            done
                        } > docker-secrets-check.txt

                        if grep -qF -- "$MYSQL_ROOT_PASSWORD" docker-secrets-check.txt; then
                            rm -f docker-secrets-check.txt
                            echo "ECHEC : le mot de passe est visible dans docker inspect"
                            exit 1
                        fi
                        echo "" >> docker-secrets-check.txt
                        echo "RESULTAT : mot de passe absent de docker inspect (transmis uniquement par Docker Secrets)" >> docker-secrets-check.txt
                        echo " -> Docker Secrets : mot de passe absent de docker inspect"
                    '''
                }
                sh '''
                    for i in $(seq 1 24); do
                        if curl -sf http://localhost:8089/timesheet-devops/actuator/health; then
                            echo " -> application UP (Docker Compose)"
                            exit 0
                        fi
                        sleep 5
                    done
                    echo "L'application n'a pas demarre a temps"
                    exit 1
                '''
            }
            post {
                always {
                    sh '''
                        docker compose -p timesheet-pipeline down || true
                        rm -rf .secrets
                    '''
                    archiveArtifacts artifacts: 'docker-secrets-check.txt', allowEmptyArchive: true
                }
            }
        }

        stage('Kubernetes Secret (Vault)') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
                    withVault(configuration: [vaultUrl: 'http://127.0.0.1:8200', vaultCredentialId: 'vault-approle', engineVersion: 2], vaultSecrets: [[path: 'secret/timesheet/mysql', engineVersion: 2, secretValues: [[envVar: 'MYSQL_ROOT_PASSWORD', vaultKey: 'root_password']]]]) {
                        sh '''
                            umask 077
                            TMP=$(mktemp)
                            printf '%s' "$MYSQL_ROOT_PASSWORD" > "$TMP"
                            kubectl apply -f k8s/namespace.yaml
                            kubectl create secret generic mysql-secret -n timesheet \
                                --from-file=MYSQL_ROOT_PASSWORD="$TMP" \
                                --dry-run=client -o yaml | kubectl apply -f -
                            rm -f "$TMP"
                            {
                                echo "=== Synchronisation Vault -> Kubernetes ==="
                                date
                                echo "Source : Vault, chemin secret/timesheet/mysql (identite AppRole jenkins)"
                                echo ""
                                kubectl describe secret mysql-secret -n timesheet
                            } > k8s-secret-report.txt
                            echo " -> Secret Kubernetes mysql-secret synchronise depuis Vault"
                        '''
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'k8s-secret-report.txt', allowEmptyArchive: true
                }
            }
        }

        stage('Kubernetes Deploy') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
                    sh '''
                        kubectl apply -f k8s/namespace.yaml -f k8s/mysql.yaml
                        sed "s|timesheet-devops:latest|timesheet-devops:${IMAGE_TAG}|" k8s/app.yaml | kubectl apply -f -
                    '''
                }
            }
        }

        stage('Kubernetes Verification') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
                    sh '''
                        kubectl rollout status deployment/mysqldb -n timesheet --timeout=300s
                        kubectl rollout status deployment/timesheet-app -n timesheet --timeout=300s
                        kubectl get pods -n timesheet -o wide
                        NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
                        curl -sf --retry 12 --retry-delay 5 --retry-connrefused --retry-all-errors http://$NODE_IP:30089/timesheet-devops/actuator/health
                        echo " -> application UP (Kubernetes)"
                    '''
                }
            }
        }

        stage('DAST (sqlmap)') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
                    sh '''
                        NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
                        rm -rf sqlmap-report
                        sqlmap -u "http://$NODE_IP:30089/timesheet-devops/user/retrieve-user/1*" \
                            --batch --dbms=mysql --level=3 --risk=1 \
                            --flush-session --output-dir=sqlmap-report | tee sqlmap-output.txt
                        if grep -q "identified the following injection point" sqlmap-output.txt || [ -s "sqlmap-report/$NODE_IP/log" ]; then
                            echo "INJECTION SQL DETECTEE : deploiement refuse"
                            exit 1
                        fi
                        echo " -> aucune injection SQL detectee"
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'sqlmap-output.txt', allowEmptyArchive: true
                }
            }
        }

        stage('Security Smoke Tests (ZAP + nmap)') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
                    sh '''
                        NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')

                        rm -rf zap-reports
                        mkdir -m 777 zap-reports
                        set +e
                        docker run --rm --network host -v "$PWD/zap-reports:/zap/wrk/:rw" \
                            ghcr.io/zaproxy/zaproxy:stable zap-baseline.py \
                            -t "http://$NODE_IP:30089/timesheet-devops/user/retrieve-all-users" \
                            -r zap-report.html -J zap-report.json
                        ZAP_RC=$?
                        set -e
                        echo "Code de sortie ZAP : $ZAP_RC"
                        if [ "$ZAP_RC" -eq 1 ] || [ "$ZAP_RC" -ge 3 ]; then
                            echo "ZAP : alerte FAIL ou erreur du scan, deploiement refuse"
                            exit 1
                        fi
                        echo " -> ZAP : aucune alerte FAIL (avertissements dans le rapport)"

                        ALLOWED_PORTS="30089"
                        nmap -sV -p 30000-32767 -oN nmap-report.txt "$NODE_IP"
                        OPEN=$(grep -E '^[0-9]+/tcp +open' nmap-report.txt | cut -d/ -f1 | tr '\\n' ' ')
                        echo "Ports NodePort ouverts : $OPEN"
                        for p in $OPEN; do
                            case " $ALLOWED_PORTS " in
                                *" $p "*) ;;
                                *) echo "nmap : port inattendu $p, deploiement refuse"; exit 1 ;;
                            esac
                        done
                        echo " -> nmap : seuls les ports autorises sont exposes ($ALLOWED_PORTS)"
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'zap-reports/*, nmap-report.txt', allowEmptyArchive: true
                }
            }
        }

        stage('Configuration Safety Checks (OSQuery)') {
            steps {
                sh '''
                    ALLOWED_PRIVILEGED="/minikube"
                    rm -rf osquery-reports
                    mkdir osquery-reports
                    cd osquery-reports
                    log() { echo "$1" | tee -a summary.txt; }

                    osqueryi --json "SELECT username, uid, shell FROM users WHERE uid = 0;" > uid0-accounts.json
                    osqueryi --json "SELECT name, image, privileged FROM docker_containers WHERE state = 'running';" > running-containers.json
                    osqueryi --json "SELECT name, image FROM docker_containers WHERE state = 'running' AND privileged = 1;" > privileged-containers.json
                    osqueryi --json "SELECT c.name, m.source, m.destination FROM docker_container_mounts m JOIN docker_containers c ON c.id = m.id WHERE m.source LIKE '%docker.sock%';" > docker-socket-mounts.json
                    osqueryi --json "SELECT DISTINCT port, address, protocol FROM listening_ports WHERE address IN ('0.0.0.0', '::') AND port > 0 ORDER BY port;" > listening-ports.json

                    log "=== Configuration Safety Checks (OSQuery) ==="
                    log "$(date)"
                    FAILED=0

                    UID0=$(grep -o '"username":"[^"]*"' uid0-accounts.json | cut -d'"' -f4 | tr '\\n' ' ')
                    log "Regle 1 - comptes uid 0 : $UID0"
                    if [ "$UID0" != "root " ]; then
                        log "  ECHEC : un compte autre que root a l'uid 0"
                        FAILED=1
                    else
                        log "  OK : seul root a l'uid 0"
                    fi

                    PRIV=$(grep -o '"name":"[^"]*"' privileged-containers.json | cut -d'"' -f4 | tr '\\n' ' ')
                    log "Regle 2 - conteneurs privilegies : ${PRIV:-aucun}"
                    for c in $PRIV; do
                        case " $ALLOWED_PRIVILEGED " in
                            *" $c "*) log "  OK : $c est une exception justifiee (noeud Kubernetes Minikube)" ;;
                            *) log "  ECHEC : conteneur privilegie non autorise : $c"; FAILED=1 ;;
                        esac
                    done

                    SOCK=$(grep -o '"name":"[^"]*"' docker-socket-mounts.json | cut -d'"' -f4 | tr '\\n' ' ')
                    log "Regle 3 - conteneurs avec acces au socket Docker : ${SOCK:-aucun}"
                    if [ -n "$SOCK" ]; then
                        log "  ECHEC : acces au socket Docker = controle total de la machine"
                        FAILED=1
                    else
                        log "  OK : aucun conteneur n'a acces au socket Docker"
                    fi

                    log "Info - ports ouverts sur toutes les interfaces : voir listening-ports.json"

                    if [ "$FAILED" -ne 0 ]; then
                        log "RESULTAT : configuration non conforme, deploiement refuse"
                        exit 1
                    fi
                    log "RESULTAT : configuration conforme"
                    echo " -> OSQuery : configuration conforme aux 3 regles"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'osquery-reports/*', allowEmptyArchive: true
                }
            }
        }

        stage('Intrusion Detection (fail2ban)') {
            steps {
                sh '''
                    F2B="sudo -n /usr/bin/fail2ban-client"
                    FILTER=/etc/fail2ban/filter.d/jenkins-auth.conf
                    rm -rf fail2ban-reports
                    mkdir fail2ban-reports
                    cd fail2ban-reports
                    log() { echo "$1" | tee -a summary.txt; }

                    log "=== Intrusion Detection (fail2ban) ==="
                    log "$(date)"
                    FAILED=0

                    STATE=$(systemctl is-active fail2ban || true)
                    log "Regle 1 - service fail2ban : $STATE"
                    if [ "$STATE" = "active" ]; then
                        log "  OK : fail2ban est actif"
                    else
                        log "  ECHEC : fail2ban n'est pas actif"
                        FAILED=1
                    fi

                    $F2B status > global-status.txt 2>&1 || true
                    $F2B status jenkins-auth > jail-status.txt 2>&1 || true
                    if grep -q "jenkins-auth" global-status.txt; then
                        log "Regle 2 - jail jenkins-auth : active"
                        log "  OK : le login Jenkins est protege"
                    else
                        log "Regle 2 - jail jenkins-auth : absente"
                        log "  ECHEC : la protection du login Jenkins est desactivee"
                        FAILED=1
                    fi

                    MAXRETRY=$($F2B get jenkins-auth maxretry 2>/dev/null || echo 0)
                    FINDTIME=$($F2B get jenkins-auth findtime 2>/dev/null || echo 0)
                    BANTIME=$($F2B get jenkins-auth bantime 2>/dev/null || echo 0)
                    log "Regle 3 - politique : maxretry=$MAXRETRY, findtime=${FINDTIME}s, bantime=${BANTIME}s"
                    if [ "$MAXRETRY" -ge 1 ] 2>/dev/null && [ "$MAXRETRY" -le 5 ] && [ "$BANTIME" -ge 600 ] 2>/dev/null; then
                        log "  OK : 5 essais maximum, bannissement d'au moins 10 minutes"
                    else
                        log "  ECHEC : politique trop permissive (attendu : maxretry <= 5, bantime >= 600)"
                        FAILED=1
                    fi

                    match() { fail2ban-regex "$1" "$FILTER" 2>/dev/null | grep -o "[0-9]* matched" | head -1 | cut -d" " -f1; }
                    L_FAIL4='203.0.113.7 - - [04/Oct/2026:19:22:09 +0100] "GET /loginError HTTP/1.1" 401 2567 "-" "curl"'
                    L_FAIL6='[2001:db8:0:0:0:0:0:7] - - [04/Oct/2026:19:22:09 +0100] "GET /loginError HTTP/1.1" 401 2567 "-" "curl"'
                    L_OK='203.0.113.7 - - [04/Oct/2026:19:22:09 +0100] "GET /login HTTP/1.1" 200 2567 "-" "curl"'
                    M4=$(match "$L_FAIL4")
                    M6=$(match "$L_FAIL6")
                    MOK=$(match "$L_OK")
                    log "Regle 4 - test du filtre : echec IPv4=$M4, echec IPv6=$M6, page normale=$MOK"
                    if [ "$M4" = "1" ] && [ "$M6" = "1" ] && [ "$MOK" = "0" ]; then
                        log "  OK : le filtre detecte les echecs (IPv4 et IPv6) sans faux positif"
                    else
                        log "  ECHEC : le filtre ne se comporte plus comme attendu (attendu : 1, 1, 0)"
                        FAILED=1
                    fi

                    BANNED=$(grep "Banned IP list" jail-status.txt | cut -d: -f2- | xargs)
                    TOTAL=$(grep "Total banned" jail-status.txt | awk '{print $NF}')
                    log "Info - IP actuellement bannies : ${BANNED:-aucune} (total depuis le demarrage : ${TOTAL:-0})"

                    if [ "$FAILED" -ne 0 ]; then
                        log "RESULTAT : protection anti brute-force non conforme"
                        exit 1
                    fi
                    log "RESULTAT : protection anti brute-force conforme"
                    echo " -> fail2ban : login Jenkins protege, 4 regles respectees"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'fail2ban-reports/*', allowEmptyArchive: true
                }
            }
        }

        stage('Prometheus') {
            steps {
                sh """
                    for i in \$(seq 1 12); do
                        STATE=\$(curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=up{job="timesheet-app"}' | python3 -c "import json,sys; r=json.load(sys.stdin)['data']['result']; print(r[0]['value'][1] if r else 'absent')")
                        echo "Prometheus -> timesheet-app : \$STATE"
                        if [ "\$STATE" = "1" ]; then
                            echo " -> metriques collectees par Prometheus"
                            exit 0
                        fi
                        sleep 10
                    done
                    echo "Prometheus ne collecte pas les metriques de l'application"
                    exit 1
                """
            }
        }
    }
}
