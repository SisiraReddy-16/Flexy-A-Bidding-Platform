```groovy
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
    }
}
```
