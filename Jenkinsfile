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
                sh '''#!/bin/bash
                export PATH="$USER/miniconda2/bin:$PATH";
                echo $PATH;
                source activate mmeds-stable;
                python setup.py install;
                '''
            }
        }
        stage('Test') {
            steps {
                sh 'bash pytest --cov=mmeds -W ignore::DeprecationWarning -W ignore::FutureWarning -s ./mmeds/tests/unit -x --durations=0'
            }
            post {
                always {
                    sh 'bash <(curl -s https://codecov.io/bash) -cF unit'
                }
            }
        }
    }
}
