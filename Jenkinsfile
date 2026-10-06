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
                        set -e

                        export AWS_DEFAULT_REGION=ap-south-1

                        aws ecr get-login-password --region $AWS_DEFAULT_REGION |
                        docker login \
                            --username AWS \
                            --password-stdin \
                            994748687548.dkr.ecr.ap-south-1.amazonaws.com

                        docker build -t flexy-backend:${BUILD_NUMBER} .

                        docker tag \
                            flexy-backend:${BUILD_NUMBER} \
                            994748687548.dkr.ecr.ap-south-1.amazonaws.com/flexy-backend:${BUILD_NUMBER}

                        docker push \
                            994748687548.dkr.ecr.ap-south-1.amazonaws.com/flexy-backend:${BUILD_NUMBER}
                    '''
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                withCredentials([
                    sshUserPrivateKey(
                        credentialsId: 'k8s-deploy-key',
                        keyFileVariable: 'SSH_KEY',
                        usernameVariable: 'SSH_USER'
                    )
                ]) {
                    sh '''
                        set -e

                        echo "Deploying build ${BUILD_NUMBER} to Kubernetes..."

                        ssh \
                            -i "$SSH_KEY" \
                            -o StrictHostKeyChecking=accept-new \
                            -o ConnectTimeout=10 \
                            "$SSH_USER@10.0.1.186" \
                            "bash -s -- '${BUILD_NUMBER}'" <<'REMOTE'

set -euo pipefail

TAG="$1"

ECR_REGISTRY="994748687548.dkr.ecr.ap-south-1.amazonaws.com"
IMAGE="$ECR_REGISTRY/flexy-backend:$TAG"

echo "Image to deploy: $IMAGE"

echo "Refreshing ECR pull secret..."

ECR_PASSWORD="$(aws ecr get-login-password --region ap-south-1)"

sudo k3s kubectl create secret docker-registry ecr-secret \
    --docker-server="$ECR_REGISTRY" \
    --docker-username=AWS \
    --docker-password="$ECR_PASSWORD" \
    --docker-email=unused@example.com \
    --dry-run=client \
    -o yaml |
sudo k3s kubectl apply -f -

echo "Updating Kubernetes deployment..."

sudo k3s kubectl set image deployment/flexy-backend \
    flexy-backend="$IMAGE"

echo "Waiting for rollout..."

sudo k3s kubectl rollout status deployment/flexy-backend \
    --timeout=180s

echo "Deployment successful."

sudo k3s kubectl get pods \
    -l app=flexy-backend \
    -o wide

REMOTE
                    '''
                }
            }
        }
    }
}