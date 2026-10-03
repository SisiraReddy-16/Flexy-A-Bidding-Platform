pipeline {

    agent any

    stages {

        stage('Checkout') {
            steps {
                echo 'Checking out Flexy project...'
                checkout scm
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

