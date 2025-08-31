import unittest
import requests
import requests_mock
import os
import json
from unittest.mock import mock_open, patch

# Assuming the functions to be tested are in container_image_checker.py
# If not, ensure they are imported correctly.
from container_image_checker import parse_image, check_docker_hub_image, check_ghcr_image, check_codeberg_image, check_image_repository, process_json_files, get_images_from_json

class TestContainerImageChecker(unittest.TestCase):
    """
    Test suite for the container_image_checker functions.
    """

    def test_parse_image(self):
        """
        Test the parse_image function for different image string formats.
        """
        # Test a standard Docker Hub image with a tag
        registry, owner, container, tag = parse_image("ubuntu:20.04")
        self.assertEqual((registry, owner, container, tag), ("docker.io", "library", "ubuntu", "20.04"))

        # Test a standard Docker Hub image with no tag
        registry, owner, container, tag = parse_image("ubuntu")
        self.assertEqual((registry, owner, container, tag), ("docker.io", "library", "ubuntu", "latest"))

        # Test a user-owned Docker Hub image
        registry, owner, container, tag = parse_image("myuser/myimage:v1.0")
        self.assertEqual((registry, owner, container, tag), ("docker.io", "myuser", "myimage", "v1.0"))

        # Test a ghcr.io image
        registry, owner, container, tag = parse_image("ghcr.io/myuser/myimage:latest")
        self.assertEqual((registry, owner, container, tag), ("ghcr.io", "myuser", "myimage", "latest"))

        # Test a codeberg.org image with no explicit tag in the string
        registry, owner, container, tag = parse_image("codeberg.org/phillxnet/bareos-file")
        self.assertEqual((registry, owner, container, tag), ("codeberg.org", "phillxnet", "bareos-file", "latest"))
        
        # Test an image with a tag provided by the JSON, even if the image string doesn't have one
        registry, owner, container, tag = parse_image("linuxserver/booksonic", tag_from_json="2.1")
        self.assertEqual((registry, owner, container, tag), ("docker.io", "linuxserver", "booksonic", "2.1"))
    
    @requests_mock.Mocker()
    def test_check_docker_hub_image_success(self, m):
        """
        Test check_docker_hub_image for a successful response.
        """
        mock_response = {"last_updated": "2023-01-01T12:00:00Z"}
        m.get('https://hub.docker.com/v2/repositories/library/ubuntu/tags/latest', json=mock_response, status_code=200)

        result = check_docker_hub_image("library", "ubuntu", "latest")
        self.assertEqual(result, {"available": True, "last_published": "2023-01-01T12:00:00Z"})
    
    @requests_mock.Mocker()
    def test_check_docker_hub_image_not_found(self, m):
        """
        Test check_docker_hub_image for a 404 Not Found error.
        """
        m.get('https://hub.docker.com/v2/repositories/nonexistent/image/tags/nonexistent', status_code=404)
        result = check_docker_hub_image("nonexistent", "image", "nonexistent")
        self.assertEqual(result, {"available": False, "last_published": "N/A"})

    @requests_mock.Mocker()
    def test_check_ghcr_image_success(self, m):
        """
        Test check_ghcr_image for a successful response.
        """
        mock_response = {"updated_at": "2023-02-02T10:00:00Z"}
        m.get('https://api.github.com/users/myuser/packages/container/myimage', json=mock_response, status_code=200)
        
        result = check_ghcr_image("myuser", "myimage", "latest", github_token="fake_token")
        self.assertEqual(result, {"available": True, "last_published": "2023-02-02T10:00:00Z"})

    @requests_mock.Mocker()
    def test_check_ghcr_image_not_found(self, m):
        """
        Test check_ghcr_image for a 404 Not Found error.
        """
        m.get('https://api.github.com/users/myuser/packages/container/nonexistent', status_code=404)
        result = check_ghcr_image("myuser", "nonexistent", "latest", github_token="fake_token")
        self.assertEqual(result, {"available": False, "last_published": "N/A"})

    @requests_mock.Mocker()
    def test_check_codeberg_image_success(self, m):
        """
        Test check_codeberg_image for a successful response.
        """
        mock_response = {"created_at": "2023-03-03T08:00:00Z"}
        m.get('https://codeberg.org/api/v1/packages/phillxnet/bareos-file/latest', json=mock_response, status_code=200)
        
        result = check_codeberg_image("phillxnet", "bareos-file", "latest")
        self.assertEqual(result, {"available": True, "last_published": "2023-03-03T08:00:00Z"})

    @requests_mock.Mocker()
    def test_check_codeberg_image_not_found(self, m):
        """
        Test check_codeberg_image for a 404 Not Found error.
        """
        m.get('https://codeberg.org/api/v1/packages/phillxnet/nonexistent/latest', status_code=404)
        result = check_codeberg_image("phillxnet", "nonexistent", "latest")
        self.assertEqual(result, {"available": False, "last_published": "N/A"})

    @requests_mock.Mocker()
    @patch('container_image_checker.check_docker_hub_image')
    @patch('container_image_checker.check_ghcr_image')
    @patch('container_image_checker.check_codeberg_image')
    def test_check_image_repository(self, mock_codeberg, mock_ghcr, mock_docker, m):
        """
        Test the dispatcher function to ensure it calls the correct registry checker.
        """
        # Test Docker Hub dispatch
        mock_docker.return_value = {"available": True, "last_published": "mock_date"}
        check_image_repository("ubuntu:latest")
        mock_docker.assert_called_once()
        self.assertFalse(mock_ghcr.called)
        self.assertFalse(mock_codeberg.called)

        # Reset mocks
        mock_docker.reset_mock()
        mock_ghcr.reset_mock()
        mock_codeberg.reset_mock()

        # Test ghcr.io dispatch
        mock_ghcr.return_value = {"available": True, "last_published": "mock_date"}
        check_image_repository("ghcr.io/myuser/myimage:latest")
        self.assertFalse(mock_docker.called)
        mock_ghcr.assert_called_once()
        self.assertFalse(mock_codeberg.called)
        
        # Reset mocks
        mock_docker.reset_mock()
        mock_ghcr.reset_mock()
        mock_codeberg.reset_mock()

        # Test codeberg.org dispatch
        mock_codeberg.return_value = {"available": True, "last_published": "mock_date"}
        check_image_repository("codeberg.org/phillxnet/bareos-file")
        self.assertFalse(mock_docker.called)
        self.assertFalse(mock_ghcr.called)
        mock_codeberg.assert_called_once()


    @patch('os.listdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    @patch('container_image_checker.check_image_repository')
    def test_process_json_files(self, mock_check_repo, mock_json_load, mock_open, mock_listdir):
        """
        Test process_json_files with mocked file system and network calls.
        """
        # Setup mock file structure and content
        mock_listdir.return_value = ['app.json', 'other.json']
        mock_json_load.side_effect = [
            {"App": {"containers": {"container1": {"image": "ubuntu", "tag": "latest"}}}},
            {"Other": {"containers": {"container2": {"image": "ghcr.io/test/image", "tag": "v1.0"}}}}
        ]

        # Setup mock network check
        mock_check_repo.side_effect = [
            {"available": True, "last_published": "2023-01-01"},
            {"available": True, "last_published": "2023-02-02"}
        ]

        # Run the function
        results = process_json_files('./configs', None, None, False)

        # Assertions
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['Rockon'], 'App')
        self.assertEqual(results[0]['image'], 'ubuntu')
        self.assertEqual(results[0]['Availability'], True)
        self.assertEqual(results[1]['Rockon'], 'Other')
        self.assertEqual(results[1]['image'], 'ghcr.io/test/image')
        self.assertEqual(results[1]['Availability'], True)

    @patch('os.listdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_get_images_from_json(self, mock_json_load, mock_open, mock_listdir):
        """
        Test get_images_from_json with mocked file system.
        """
        mock_listdir.return_value = ['app.json', 'another.json']
        mock_json_load.side_effect = [
            {"App": {"containers": {"container1": {"image": "ubuntu", "tag": "latest"}}}},
            {"Another": {"containers": {"container2": {"image": "ghcr.io/test/image"}}}}
        ]

        images = get_images_from_json('./configs')

        self.assertEqual(images, ['ghcr.io/test/image:latest', 'ubuntu:latest'])
        self.assertEqual(mock_listdir.call_count, 1)
        self.assertEqual(mock_open.call_count, 2)


if __name__ == "__main__":
    unittest.main()
