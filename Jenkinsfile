pipeline {

    agent any

    stages {

        stage('Checkout') {
            steps {
                echo 'Checking out Flexy project...'

                git branch: 'main',
                    url: 'https://github.com/SisiraReddy-16/Flexy-A-Bidding-Platform.git'
            }
        }

        stage('Maven Build') {
            steps {
                echo 'Building Flexy application...'

                sh '''
                    mvn clean package -DskipTests
                '''
            }
        }

        stage('Verify Build') {
            steps {
                echo 'Checking generated JAR...'

                sh '''
                    ls -lh target/
                '''
            }
        }
    }

    post {

        success {
            echo '''
            ==========================================
              FLEXY BUILD SUCCESSFUL
            ==========================================
            Maven successfully created the JAR.
            ==========================================
            '''
        }

        failure {
            echo '''
            ==========================================
              FLEXY BUILD FAILED
            ==========================================
            Check the Jenkins console output.
            ==========================================
            '''
        }
    }
}