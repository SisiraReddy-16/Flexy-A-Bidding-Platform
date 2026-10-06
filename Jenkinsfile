pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                git branch: 'main',
                    url: 'https://github.com/SisiraReddy-16/Flexy-A-Bidding-Platform.git'
            }
        }

        stage('Maven Test') {
            steps {
                sh 'mvn -version'
            }
        }

        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv('SonarQube') {
                    sh 'mvn org.sonarsource.scanner.maven:sonar-maven-plugin:sonar'
                }
            }
        }

        stage('Docker Build & Push to ECR') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'awscreds',
                        usernameVariable: 'AWS_ACCESS_KEY_ID',
                        passwordVariable: 'AWS_SECRET_ACCESS_KEY'
                    )
                ]) {
                    sh '''
                        export AWS_DEFAULT_REGION=ap-south-1

                        aws ecr get-login-password --region $AWS_DEFAULT_REGION |
                        docker login --username AWS --password-stdin 994748687548.dkr.ecr.ap-south-1.amazonaws.com

                        docker build -t flexy-backend:${BUILD_NUMBER} .

                        docker tag flexy-backend:${BUILD_NUMBER} \
                        994748687548.dkr.ecr.ap-south-1.amazonaws.com/flexy-backend:${BUILD_NUMBER}

                        docker push \
                        994748687548.dkr.ecr.ap-south-1.amazonaws.com/flexy-backend:${BUILD_NUMBER}
                    '''
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                sh '''
                    set -e

                    ssh \
                      -i /var/lib/jenkins/.ssh/k8s_deploy_key \
                      -o StrictHostKeyChecking=accept-new \
                      ubuntu@10.0.1.186 "bash -s -- '${BUILD_NUMBER}'" <<'REMOTE'

set -euo pipefail

TAG="$1"
ECR_REGISTRY="994748687548.dkr.ecr.ap-south-1.amazonaws.com"
IMAGE="$ECR_REGISTRY/flexy-backend:$TAG"

echo "Refreshing ECR pull secret..."

ECR_PASSWORD="$(aws ecr get-login-password --region ap-south-1)"

sudo k3s kubectl create secret docker-registry ecr-secret \
    --docker-server="$ECR_REGISTRY" \
    --docker-username=AWS \
    --docker-password="$ECR_PASSWORD" \
    --docker-email=unused@example.com \
    --dry-run=client \
    -o yaml | sudo k3s kubectl apply -f -

echo "Deploying image: $IMAGE"

sudo k3s kubectl set image deployment/flexy-backend \
    flexy-backend="$IMAGE"

echo "Waiting for Kubernetes rollout..."

sudo k3s kubectl rollout status deployment/flexy-backend \
    --timeout=180s

echo "Deployment completed."

sudo k3s kubectl get pods -l app=flexy-backend -o wide

REMOTE
                '''
            }
        }
    }
}