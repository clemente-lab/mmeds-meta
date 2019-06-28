pipeline {
    agent {
                docker {
                        image 'python3:latest'
                }
        stages {
            stage('Build') {
            }
            steps {
                sh 'python setup.py install'
            }
        }
        stage('Test') {
            steps {
                sh 'pytest --cov=mmeds -W ignore::DeprecationWarning -W ignore::FutureWarning -s ./mmeds/tests/unit -x --durations=0'
            }
            post {
                always {
                    sh 'bash <(curl -s https://codecov.io/bash) -cF unit'
                }
            }
        }
    }
}
