"""
Cloudinary Service for Dev Project Organizer
Handles image uploads and management using Cloudinary
"""

import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class CloudinaryService:
    """Manages image uploads and operations with Cloudinary"""
    
    def __init__(self):
        """Initialize Cloudinary with environment variables"""
        self.configured = False
        self._configure()
    
    def _configure(self):
        """Configure Cloudinary using environment variables"""
        try:
            cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
            api_key = os.getenv('CLOUDINARY_API_KEY')
            api_secret = os.getenv('CLOUDINARY_API_SECRET')
            
            if not all([cloud_name, api_key, api_secret]):
                logger.warning("Cloudinary credentials not found in environment variables")
                return
            
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True
            )
            
            self.configured = True
            logger.info("Cloudinary configured successfully")
            
        except Exception as e:
            logger.error(f"Error configuring Cloudinary: {str(e)}")
            self.configured = False
    
    def is_configured(self) -> bool:
        """Check if Cloudinary is properly configured"""
        return self.configured
    
    def upload_image(self, file, folder: str = "dev-organizer/notes") -> Optional[Dict]:
        """
        Upload an image to Cloudinary
        
        Args:
            file: File object (from Flask request.files)
            folder: Cloudinary folder path to organize images
            
        Returns:
            Dictionary with upload results containing:
            - public_id: Cloudinary public ID
            - secure_url: HTTPS URL to access the image
            - url: HTTP URL to access the image
            - format: Image format (jpg, png, etc.)
            - width: Image width in pixels
            - height: Image height in pixels
            - bytes: File size in bytes
            - created_at: Upload timestamp
            
            Returns None if upload fails
        """
        if not self.configured:
            logger.error("Cloudinary is not configured")
            return None
        
        try:
            # Upload to Cloudinary with automatic optimization
            result = cloudinary.uploader.upload(
                file,
                folder=folder,
                resource_type="image",
                # Optimize images automatically
                quality="auto",
                fetch_format="auto",
                # Generate unique filename
                use_filename=True,
                unique_filename=True,
                # Add transformations for optimization
                transformation=[
                    {'quality': 'auto:good'},
                    {'fetch_format': 'auto'}
                ]
            )
            
            logger.info(f"Image uploaded successfully: {result.get('public_id')}")
            
            return {
                'public_id': result.get('public_id'),
                'secure_url': result.get('secure_url'),
                'url': result.get('url'),
                'format': result.get('format'),
                'width': result.get('width'),
                'height': result.get('height'),
                'bytes': result.get('bytes'),
                'created_at': result.get('created_at'),
                'resource_type': result.get('resource_type'),
            }
            
        except Exception as e:
            logger.error(f"Error uploading image to Cloudinary: {str(e)}", exc_info=True)
            return None
    
    def delete_image(self, public_id: str) -> bool:
        """
        Delete an image from Cloudinary
        
        Args:
            public_id: The Cloudinary public_id of the image to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.configured:
            logger.error("Cloudinary is not configured")
            return False
        
        try:
            result = cloudinary.uploader.destroy(public_id)
            
            if result.get('result') == 'ok':
                logger.info(f"Image deleted successfully: {public_id}")
                return True
            else:
                logger.warning(f"Failed to delete image: {public_id}, result: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting image from Cloudinary: {str(e)}", exc_info=True)
            return False
    
    def delete_images_bulk(self, public_ids: list) -> Dict:
        """
        Delete multiple images from Cloudinary
        
        Args:
            public_ids: List of Cloudinary public_ids to delete
            
        Returns:
            Dictionary with results:
            - deleted: List of successfully deleted public_ids
            - failed: List of failed deletions
        """
        if not self.configured:
            logger.error("Cloudinary is not configured")
            return {'deleted': [], 'failed': public_ids}
        
        deleted = []
        failed = []
        
        for public_id in public_ids:
            if self.delete_image(public_id):
                deleted.append(public_id)
            else:
                failed.append(public_id)
        
        return {
            'deleted': deleted,
            'failed': failed
        }
    
    def get_image_info(self, public_id: str) -> Optional[Dict]:
        """
        Get information about an image from Cloudinary
        
        Args:
            public_id: The Cloudinary public_id of the image
            
        Returns:
            Dictionary with image information or None if not found
        """
        if not self.configured:
            logger.error("Cloudinary is not configured")
            return None
        
        try:
            result = cloudinary.api.resource(public_id)
            return result
            
        except Exception as e:
            logger.error(f"Error getting image info from Cloudinary: {str(e)}", exc_info=True)
            return None
    
    def generate_thumbnail_url(self, public_id: str, width: int = 300, height: int = 300) -> str:
        """
        Generate a thumbnail URL for an image
        
        Args:
            public_id: The Cloudinary public_id of the image
            width: Thumbnail width in pixels
            height: Thumbnail height in pixels
            
        Returns:
            URL to the thumbnail version of the image
        """
        if not self.configured:
            logger.error("Cloudinary is not configured")
            return ""
        
        try:
            url = cloudinary.CloudinaryImage(public_id).build_url(
                width=width,
                height=height,
                crop="fill",
                quality="auto",
                fetch_format="auto"
            )
            return url
            
        except Exception as e:
            logger.error(f"Error generating thumbnail URL: {str(e)}", exc_info=True)
            return ""


# Create a singleton instance
cloudinary_service = CloudinaryService()
