#!/bin/bash

isort server/ --check-only
black server/ --check
