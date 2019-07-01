pipeline {
    agent {
        docker {
            image 'mmeds-mysql-mongo:latest'
            registryUrl 'http://localhost:2375'
        }
    }
    options {
        skipStagesAfterUnstable()
    }
    stages {
        stage('Build') {
            steps {
                sh 'source activate mmeds-stable'
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
