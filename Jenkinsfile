pipeline {
    agent {
        docker {
            image 'mmeds:latest'
                registryUrl 'http://localhost:2375'
        }
    }
    options {
        skipStagesAfterUnstable()
    }
    stages {
        stage('Build') {
            steps {
                bash 'source activate mmeds-stable'
                bash 'python setup.py install'
            }
        }
        stage('Test') {
            steps {
                bash 'pytest --cov=mmeds -W ignore::DeprecationWarning -W ignore::FutureWarning -s ./mmeds/tests/unit -x --durations=0'
            }
            post {
                always {
                    sh 'bash <(curl -s https://codecov.io/bash) -cF unit'
                }
            }
        }
    }
}
