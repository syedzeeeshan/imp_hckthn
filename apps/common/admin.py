"""
Common admin configurations
"""
from django.contrib import admin

class BaseModelAdmin(admin.ModelAdmin):
    """Base admin class with common configurations"""
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_per_page = 25
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly"""
        readonly_fields = list(self.readonly_fields)
        
        if obj:  # Editing existing object
            readonly_fields.extend(['created_at'])
        
        return readonly_fields
