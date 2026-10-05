pipeline {
    agent any

    stages {
        stage('Maven Test') {
            steps {
                sh 'mvn -version'
            }
        }

        stage('SonarQube Test') {
            steps {
                withSonarQubeEnv('SonarQube') {
                    sh 'mvn sonar:sonar'
                }
            }
        }
    }
}