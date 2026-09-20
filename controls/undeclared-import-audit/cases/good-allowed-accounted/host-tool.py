"""Operator tooling run under the system interpreter, recorded in the ledger."""
import boto3


def main():
    return boto3.Session()
