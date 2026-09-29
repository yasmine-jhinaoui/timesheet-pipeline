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

        stage('Integration Test (Docker Compose)') {
            steps {
                withCredentials([string(credentialsId: 'mysql-root-password', variable: 'MYSQL_ROOT_PASSWORD')]) {
                    sh 'docker compose -p timesheet-pipeline up -d'
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
                    withCredentials([string(credentialsId: 'mysql-root-password', variable: 'MYSQL_ROOT_PASSWORD')]) {
                        sh 'docker compose -p timesheet-pipeline down'
                    }
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
                        if [ -s "sqlmap-report/$NODE_IP/log" ]; then
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
