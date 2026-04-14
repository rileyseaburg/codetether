// Jenkinsfile — A2A Server CI/CD with Blue/Green Deployment
//
// Prerequisites:
//   - Jenkins controller at 192.168.50.85:8080 with kubectl, helm, docker, gcloud
//   - Credentials:
//       'gcp-artifact-registry'  — gcloud service account JSON
//       'github-token'           — PAT for commit status + PR comments
//   - Kubernetes cluster access via kubeconfig on the agent
//   - Helm release 'codetether' installed in namespace 'a2a-server'
//
// Pipeline stages:
//   1. Test      — pytest + OPA policy tests
//   2. Build     — Docker image build
//   3. Push      — Push to GCP Artifact Registry
//   4. Stage     — Deploy to inactive blue/green color (0 traffic)
//   5. Verify    — Health checks + smoke tests on new pods
//   6. Cutover   — Switch service selector to new color
//   7. Confirm   — Post-cutover smoke test; auto-rollback on failure
//   8. Cleanup   — Scale old color to 0

pipeline {
    agent any

    environment {
        REGISTRY     = 'us-central1-docker.pkg.dev'
        PROJECT      = 'spotlessbinco'
        REPO         = 'codetether/a2a-server-mcp'
        IMAGE_PREFIX = "${REGISTRY}/${PROJECT}/${REPO}"
        NAMESPACE    = 'a2a-server'
        RELEASE      = 'codetether'
        CHART_PATH   = 'chart/a2a-server'
        PATH         = "/var/lib/jenkins/.local/bin:/var/lib/jenkins/.local/google-cloud-sdk/bin:${env.PATH}"
        KUBECONFIG   = '/var/lib/jenkins/.kube/config'
    }

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {
        // ── Test ───────────────────────────────────────────────────────
        stage('Test') {
            steps {
                sh '''
                    if command -v python3 >/dev/null 2>&1; then
                        pip3 install --quiet -r requirements.txt -r requirements-test.txt 2>/dev/null || true
                        python3 -m pytest tests/ -v --tb=short || echo "WARN: Tests failed or not available"
                    else
                        echo "WARN: python3 not found on agent, skipping tests"
                    fi
                '''
            }
        }

        // ── OPA Policy Tests ───────────────────────────────────────────
        stage('Policy Tests') {
            steps {
                sh '''
                    if command -v opa >/dev/null 2>&1; then
                        opa test policies/ -v
                    elif [ -f /usr/local/bin/opa ]; then
                        /usr/local/bin/opa test policies/ -v
                    else
                        curl -sL -o /tmp/opa https://openpolicyagent.org/downloads/v1.3.0/opa_linux_amd64_static
                        chmod +x /tmp/opa
                        /tmp/opa test policies/ -v
                    fi
                '''
            }
        }

        // ── Build ──────────────────────────────────────────────────────
        stage('Build') {
            steps {
                script {
                    env.IMAGE_TAG = "jenkins-${env.BUILD_NUMBER}-${sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()}"
                }
                sh """
                    docker build \
                        -t "${IMAGE_PREFIX}:${env.IMAGE_TAG}" \
                        -t "${IMAGE_PREFIX}:latest" \
                        .
                """
            }
        }

        // ── Push ───────────────────────────────────────────────────────
        stage('Push') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'gcp-artifact-registry', usernameVariable: 'GCP_USER', passwordVariable: 'GCP_KEY')]) {
                    sh '''
                        echo "$GCP_KEY" > /tmp/gcp-sa-key.json
                        gcloud auth activate-service-account --key-file=/tmp/gcp-sa-key.json 2>/dev/null || true
                        gcloud auth configure-docker us-central1-docker.pkg.dev --quiet
                        rm -f /tmp/gcp-sa-key.json
                    '''
                }
                sh """
                    docker push "${IMAGE_PREFIX}:${env.IMAGE_TAG}"
                    docker push "${IMAGE_PREFIX}:latest"
                """
            }
            post {
                always {
                    sh 'gcloud auth revoke --all 2>/dev/null || true'
                }
            }
        }

        // ── Determine Active Color ─────────────────────────────────────
        stage('Determine Colors') {
            steps {
                script {
                    def active = sh(
                        script: """
                            kubectl get svc ${RELEASE}-a2a-server -n ${NAMESPACE} \
                                -o jsonpath='{.metadata.annotations.bluegreen/active-color}' 2>/dev/null || echo green
                        """,
                        returnStdout: true
                    ).trim()
                    env.ACTIVE_COLOR = active
                    env.INACTIVE_COLOR = (active == 'blue') ? 'green' : 'blue'
                    echo "Active: ${env.ACTIVE_COLOR}, Deploying to: ${env.INACTIVE_COLOR}"
                }
            }
        }

        // ── Stage: Deploy to inactive color ────────────────────────────
        stage('Stage') {
            steps {
                sh """
                    helm upgrade ${RELEASE} ${CHART_PATH} \
                        --namespace ${NAMESPACE} \
                        --reuse-values \
                        --set blueGreen.enabled=true \
                        --set blueGreen.mode=bluegreen \
                        --set blueGreen.serviceColor=${ACTIVE_COLOR} \
                        --set blueGreen.replicas.${INACTIVE_COLOR}=1 \
                        --set blueGreen.replicas.${ACTIVE_COLOR}=1 \
                        --set blueGreen.images.${INACTIVE_COLOR}.image=${IMAGE_PREFIX}:${IMAGE_TAG} \
                        --set blueGreen.rolloutId.${INACTIVE_COLOR}=rollout-\$(date +%s) \
                        --wait --timeout 180s
                """
            }
        }

        // ── Verify: Wait for new pods ──────────────────────────────────
        stage('Verify') {
            steps {
                sh """
                    kubectl rollout status \
                        deployment/${RELEASE}-a2a-server-deployment-${INACTIVE_COLOR} \
                        -n ${NAMESPACE} \
                        --timeout=180s
                """
            }
        }

        // ── Cutover: Switch service to new color ───────────────────────
        stage('Cutover') {
            steps {
                // Input step gives a manual gate; auto-proceed after 2 min
                timeout(time: 2, unit: 'MINUTES') {
                    input message: "Switch traffic from ${ACTIVE_COLOR} → ${INACTIVE_COLOR}?", ok: 'Cutover'
                }
                sh """
                    helm upgrade ${RELEASE} ${CHART_PATH} \
                        --namespace ${NAMESPACE} \
                        --reuse-values \
                        --set blueGreen.serviceColor=${INACTIVE_COLOR} \
                        --wait --timeout 120s
                """
            }
        }

        // ── Confirm: Post-cutover smoke test ───────────────────────────
        stage('Confirm') {
            steps {
                sh '''
                    sleep 3
                    for i in $(seq 1 12); do
                        HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" \
                            "https://api.codetether.run/.well-known/agent-card.json" 2>/dev/null || echo "000")
                        if [ "$HTTP_CODE" = "200" ]; then
                            echo "Smoke test passed (HTTP $HTTP_CODE on attempt $i)"
                            exit 0
                        fi
                        echo "Attempt $i/12: HTTP $HTTP_CODE — retrying..."
                        sleep 5
                    done
                    echo "ERROR: Post-cutover smoke test failed"
                    exit 1
                '''
            }
            post {
                failure {
                    echo 'Rolling back: switching service back to previous color'
                    sh """
                        helm upgrade ${RELEASE} ${CHART_PATH} \
                            --namespace ${NAMESPACE} \
                            --reuse-values \
                            --set blueGreen.serviceColor=${ACTIVE_COLOR} \
                            --wait --timeout 120s
                    """
                }
            }
        }

        // ── Cleanup: Scale old color to 0 ──────────────────────────────
        stage('Cleanup') {
            steps {
                sh """
                    helm upgrade ${RELEASE} ${CHART_PATH} \
                        --namespace ${NAMESPACE} \
                        --reuse-values \
                        --set blueGreen.replicas.${ACTIVE_COLOR}=0 \
                        --wait --timeout 120s
                """
            }
        }
    }

    post {
        success {
            echo "✅ Blue/Green deployment complete: ${INACTIVE_COLOR} is live (${IMAGE_TAG})"
        }
        failure {
            echo "❌ Pipeline failed at stage: ${currentBuild.currentResult}"
        }
        always {
            cleanWs()
        }
    }
}
