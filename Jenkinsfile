pipeline {

    agent any

    tools {
        maven 'Maven 3.9.16'
    }

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
                echo 'Building Flexy Spring Boot application...'

                sh '''
                    mvn clean package -DskipTests
                '''
            }
        }

        stage('Verify Build') {
            steps {
                echo 'Checking generated JAR...'

                sh '''
                    echo "Generated files:"
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

            GitHub checkout       : SUCCESS
            Maven build           : SUCCESS
            JAR generation        : SUCCESS

            Next stage:
            Docker image build

            ==========================================
            '''
        }

        failure {
            echo '''
            ==========================================
              FLEXY BUILD FAILED
            ==========================================

            Check the failed stage in the Jenkins
            console output.

            ==========================================
            '''
        }
    }
}
