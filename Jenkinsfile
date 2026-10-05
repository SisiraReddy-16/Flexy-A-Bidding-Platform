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
                        credentialsId: 'aws-ecr',
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
    }
}

