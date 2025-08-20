import requests
import semver
import json
import os
import zipfile
import shutil
import tempfile
from pathlib import Path
from services import __version__ as current_version

class UpdateManager:
    def __init__(self):
        self.config = self._load_config()
        self.current_version = current_version

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def check_for_updates(self):
        """Checks for new releases on GitHub."""
        repo_owner = self.config.get('github_owner')
        repo_name = self.config.get('github_repo')
        if not repo_owner or not repo_name:
            print("GitHub repository owner or name not configured.")
            return None, None

        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            latest_release = response.json()
            latest_version = latest_release['tag_name'].lstrip('v')
            release_notes = latest_release['body']
            return latest_version, release_notes
        except requests.exceptions.RequestException as e:
            print(f"Error checking for updates: {e}")
            return None, None

    def is_new_version_available(self, latest_version):
        """Compares the latest version with the current version."""
        if not latest_version:
            return False
        return semver.compare(latest_version, self.current_version) > 0

    def download_and_apply_update(self):
        """Downloads and applies the latest update with backup and rollback support."""
        repo_owner = self.config.get('github_owner')
        repo_name = self.config.get('github_repo')
        if not repo_owner or not repo_name:
            print("GitHub repository owner or name not configured.")
            return False

        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        backup_dir = None
        temp_dir = None
        download_path = None
        
        try:
            # Get latest release info
            response = requests.get(api_url)
            response.raise_for_status()
            latest_release = response.json()
            
            if not latest_release.get('assets'):
                print("No assets found in the latest release.")
                return False

            asset = latest_release['assets'][0]
            download_url = asset['browser_download_url']
            file_name = asset['name']
            
            # Create backup directory
            project_root = Path(__file__).parent.parent
            backup_dir = project_root / "backup_before_update"
            backup_dir.mkdir(exist_ok=True)
            
            print("Creating backup of current version...")
            self._backup_current_version(backup_dir)
            
            # Download the update
            print(f"Downloading {file_name} from {download_url}...")
            download_response = requests.get(download_url, stream=True)
            download_response.raise_for_status()

            # Save to temp location
            temp_dir = tempfile.mkdtemp()
            download_path = os.path.join(temp_dir, file_name)
            with open(download_path, 'wb') as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"Downloaded update to {download_path}")
            
            # Extract and apply update
            print("Extracting and applying update...")
            self._extract_and_apply_update(download_path, project_root)
            
            print("Update applied successfully!")
            
            # Clean up
            self._cleanup_after_update(backup_dir, temp_dir)
            
            return True
            
        except Exception as e:
            print(f"Error during update: {e}")
            print("Rolling back to previous version...")
            
            if backup_dir and backup_dir.exists():
                self._rollback_update(backup_dir)
                print("Rollback completed.")
            
            # Clean up temp files
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                
            return False
    
    def _backup_current_version(self, backup_dir):
        """Creates a backup of critical files before update."""
        project_root = Path(__file__).parent.parent
        
        # Files and directories to backup
        backup_items = [
            'main.py',
            'services/',
            'views/',
            'config.json',
            'requirements.txt'
        ]
        
        for item in backup_items:
            source_path = project_root / item
            if source_path.exists():
                dest_path = backup_dir / item
                if source_path.is_file():
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, dest_path)
                elif source_path.is_dir():
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    shutil.copytree(source_path, dest_path)
    
    def _extract_and_apply_update(self, zip_path, project_root):
        """Extracts the update zip and applies it to the project."""
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Extract to temporary directory first
            temp_extract_dir = tempfile.mkdtemp()
            zip_ref.extractall(temp_extract_dir)
            
            # Find the actual project directory in the extracted files
            extracted_items = os.listdir(temp_extract_dir)
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract_dir, extracted_items[0])):
                # If there's a single directory, use that as the source
                source_dir = os.path.join(temp_extract_dir, extracted_items[0])
            else:
                # Otherwise, use the temp directory directly
                source_dir = temp_extract_dir
            
            # Copy files from extracted directory to project root
            for item in os.listdir(source_dir):
                source_item = os.path.join(source_dir, item)
                dest_item = project_root / item
                
                if os.path.isfile(source_item):
                    shutil.copy2(source_item, dest_item)
                elif os.path.isdir(source_item):
                    if dest_item.exists():
                        shutil.rmtree(dest_item)
                    shutil.copytree(source_item, dest_item)
            
            # Clean up temp extraction directory
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
    
    def _rollback_update(self, backup_dir):
        """Rolls back to the backed up version."""
        project_root = Path(__file__).parent.parent
        
        for item in backup_dir.iterdir():
            dest_path = project_root / item.name
            
            if item.is_file():
                shutil.copy2(item, dest_path)
            elif item.is_dir():
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                shutil.copytree(item, dest_path)
    
    def _cleanup_after_update(self, backup_dir, temp_dir):
        """Cleans up temporary files after successful update."""
        # Remove backup directory
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
        
        # Remove temp directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)