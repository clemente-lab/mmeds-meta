pipeline {
    agent none
    stages {
        stage('Build') {
            agent {
                docker {
                    image 'mmeds:latest'
                    registryUrl 'http://localhost:2375'
                }
            }
            steps {
                sh 'python setup.py install'
            }
        }
        stage('Test') {
            agent {
                docker {
                    image 'qnib/pytest'
                }
            }
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
