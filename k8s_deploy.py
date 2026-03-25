#!/usr/bin/env python3
"""
Kubernetes Deployment Validation and Deployment Management
"""

import subprocess
import json
import time
import sys
from typing import List, Dict, Tuple


class K8sDeployment:
    def __init__(self):
        self.namespace = "analytics"
        self.deployments = [
            "postgresql",
            "duckdb-init",
            "chronic-absenteeism-dashboard",
        ]

    def check_kubectl(self) -> bool:
        """Check if kubectl is installed"""
        try:
            subprocess.run(["kubectl", "--version"], capture_output=True, check=True)
            print("✓ kubectl is installed")
            return True
        except Exception:
            print("✗ kubectl not found. Please install Kubernetes CLI tools.")
            return False

    def check_cluster_access(self) -> bool:
        """Check if we have access to a Kubernetes cluster"""
        try:
            subprocess.run(["kubectl", "cluster-info"], capture_output=True, check=True)
            print("✓ Connected to Kubernetes cluster")
            return True
        except Exception:
            print(
                "✗ No Kubernetes cluster access. Install Minikube, Docker Desktop K8s, or connect to a cluster."
            )
            return False

    def create_namespace(self) -> bool:
        """Create analytics namespace"""
        try:
            subprocess.run(
                ["kubectl", "create", "namespace", self.namespace],
                capture_output=True,
                timeout=30,
            )
            print(f"✓ Namespace '{self.namespace}' created")
            return True
        except subprocess.CalledProcessError as e:
            if "already exists" in str(e.stderr):
                print(f"✓ Namespace '{self.namespace}' already exists")
                return True
            print(f"✗ Failed to create namespace: {e}")
            return False

    def create_secrets(self) -> bool:
        """Create database credentials secret"""
        try:
            subprocess.run(
                [
                    "kubectl",
                    "create",
                    "secret",
                    "generic",
                    "db-credentials",
                    f"--from-literal=postgres-password=vincent0408",
                    f"--namespace={self.namespace}",
                ],
                capture_output=True,
                timeout=30,
            )
            print("✓ Database credentials secret created")
            return True
        except subprocess.CalledProcessError as e:
            if "already exists" in str(e.stderr):
                print("✓ Database credentials secret already exists")
                return True
            print(f"✗ Failed to create secret: {e}")
            return False

    def apply_manifests(self, manifest_file: str) -> bool:
        """Apply Kubernetes manifests"""
        try:
            subprocess.run(
                ["kubectl", "apply", "-f", manifest_file],
                capture_output=True,
                check=True,
                timeout=60,
            )
            print(f"✓ Kubernetes manifests applied from {manifest_file}")
            return True
        except Exception as e:
            print(f"✗ Failed to apply manifests: {e}")
            return False

    def wait_for_deployment(self, deployment: str, timeout: int = 300) -> bool:
        """Wait for deployment to be ready"""
        try:
            subprocess.run(
                [
                    "kubectl",
                    "rollout",
                    "status",
                    f"deployment/{deployment}",
                    f"--namespace={self.namespace}",
                    f"--timeout={timeout}s",
                ],
                capture_output=True,
                check=True,
            )
            print(f"✓ Deployment '{deployment}' is ready")
            return True
        except Exception as e:
            print(f"✗ Deployment '{deployment}' failed: {e}")
            return False

    def get_service_status(self) -> Dict:
        """Get service status and endpoints"""
        try:
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "svc",
                    f"--namespace={self.namespace}",
                    "-o",
                    "json",
                ],
                capture_output=True,
                check=True,
                text=True,
            )
            services = json.loads(result.stdout).get("items", [])

            status = {}
            for svc in services:
                name = svc["metadata"]["name"]
                svc_type = svc["spec"].get("type", "ClusterIP")
                ports = svc["spec"].get("ports", [])

                status[name] = {
                    "type": svc_type,
                    "ports": [p["port"] for p in ports],
                    "cluster_ip": svc["spec"].get("clusterIP"),
                    "external_ip": svc["status"]
                    .get("loadBalancer", {})
                    .get("ingress", []),
                }

            return status
        except Exception as e:
            print(f"✗ Failed to get service status: {e}")
            return {}

    def get_pod_status(self) -> List[Dict]:
        """Get pod status"""
        try:
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "pods",
                    f"--namespace={self.namespace}",
                    "-o",
                    "json",
                ],
                capture_output=True,
                check=True,
                text=True,
            )
            pods = json.loads(result.stdout).get("items", [])

            status = []
            for pod in pods:
                name = pod["metadata"]["name"]
                phase = pod["status"].get("phase")
                ready_containers = sum(
                    1
                    for c in pod["status"].get("conditions", [])
                    if c["type"] == "Ready" and c["status"] == "True"
                )

                status.append(
                    {"name": name, "phase": phase, "ready": ready_containers > 0}
                )

            return status
        except Exception as e:
            print(f"✗ Failed to get pod status: {e}")
            return []

    def deploy(self, manifest_file: str) -> bool:
        """Execute full deployment"""
        print("\n" + "=" * 70)
        print("KUBERNETES DEPLOYMENT")
        print("=" * 70)

        steps = [
            ("Checking kubectl", self.check_kubectl),
            ("Checking cluster access", self.check_cluster_access),
            ("Creating namespace", self.create_namespace),
            ("Creating secrets", self.create_secrets),
            ("Applying manifests", lambda: self.apply_manifests(manifest_file)),
        ]

        for step_name, step_fn in steps:
            print(f"\n{step_name}...")
            if not step_fn():
                print(f"\n✗ Deployment failed at: {step_name}")
                return False
            time.sleep(1)

        print("\n" + "=" * 70)
        print("WAITING FOR DEPLOYMENTS TO BE READY")
        print("=" * 70)

        for deployment in self.deployments:
            print(f"\nWaiting for {deployment}...")
            if not self.wait_for_deployment(deployment):
                print(f"⚠ {deployment} failed to reach ready state")

        print("\n" + "=" * 70)
        print("DEPLOYMENT STATUS")
        print("=" * 70)

        print("\nServices:")
        services = self.get_service_status()
        for name, info in services.items():
            print(f"  {name}:")
            print(f"    Type: {info['type']}")
            print(f"    Ports: {info['ports']}")
            print(f"    ClusterIP: {info['cluster_ip']}")
            if info["external_ip"]:
                print(f"    External IP: {info['external_ip']}")

        print("\nPods:")
        pods = self.get_pod_status()
        for pod in pods:
            status = "✓" if pod["ready"] else "✗"
            print(f"  {status} {pod['name']}: {pod['phase']}")

        print("\n" + "=" * 70)
        print("✓ DEPLOYMENT COMPLETE")
        print("=" * 70)
        print(f"\nTo access the dashboard:")
        print(
            f"  kubectl port-forward svc/chronic-absenteeism-dashboard 8050:8050 -n {self.namespace}"
        )
        print(f"\nThen visit: http://localhost:8050")

        return True


def main():
    """Main deployment entry point"""
    deployer = K8sDeployment()
    success = deployer.deploy("k8s-deployment.yaml")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
