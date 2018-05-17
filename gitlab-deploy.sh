#!/bin/sh

set -e

git clone --recursive $PLAYBOOK_REPO_URL $PLAYBOOK_DIR
cd $PLAYBOOK_DIR
git crypt unlock $GIT_CRYPT_KEY
ansible-galaxy install -r install_roles.yml
ansible-playbook \
  -e d4s2_docker_image=$CONTAINER_IMAGE_RELEASE \
  -e ansible_python_interpreter=/usr/bin/python3 \
  -e docker_registry=$DOCKER_REGISTRY \
  -e docker_username=gitlab-ci-token \
  -e docker_password=$CI_JOB_TOKEN \
  -u $DEPLOY_USER \
  --private-key=$DEPLOY_KEY \
  -i inventory \
  -l $DEPLOY_GROUP \
  $DEPLOY_PLAYBOOK
