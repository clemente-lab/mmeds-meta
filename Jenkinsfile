pipeline {
    agent none
    options {
        skipStagesAfterUnstable()
    }
    stages {
        stage('Build') {
            agent {
                docker {
                    sh 'env | grep DOCKER_HOST'
                        image 'mmeds:latest'
                        registryUrl 'http://localhost:2375'
                }
            }
        }
        steps {
            sh 'python setup.py install'
        }
    }
    stage('Test') {
        agent {
            docker {
                sh 'env | grep DOCKER_HOST'
                    image 'mmeds:latest'
                    registryUrl 'http://localhost:2375'
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
