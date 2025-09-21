"""
Common serializers for Campus Club Management Suite
"""
from rest_framework import serializers

class BaseModelSerializer(serializers.ModelSerializer):
    """Base serializer with common fields"""
    
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        abstract = True

class FileUploadSerializer(serializers.Serializer):
    """Serializer for file uploads"""
    
    file = serializers.FileField()
    description = serializers.CharField(max_length=200, required=False)
    
    def validate_file(self, value):
        """Validate uploaded file"""
        # Check file size (5MB limit)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 5MB")
        
        # Check file extension
        allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx']
        extension = value.name.split('.')[-1].lower()
        
        if extension not in allowed_extensions:
            raise serializers.ValidationError(
                f"File extension '{extension}' not allowed. "
                f"Allowed extensions: {', '.join(allowed_extensions)}"
            )
        
        return value
