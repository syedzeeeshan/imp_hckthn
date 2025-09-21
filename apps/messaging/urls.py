"""
URL patterns for messaging app
Complete endpoint routing for direct messaging system
"""
from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # Conversations
    path('conversations/', views.ConversationListView.as_view(), name='conversation_list'),
    path('conversations/<uuid:id>/', views.ConversationDetailView.as_view(), name='conversation_detail'),
    path('conversations/search/', views.conversation_search, name='conversation_search'),
    
    # Messages
    path('conversations/<uuid:conversation_id>/messages/', views.ConversationMessagesView.as_view(), name='conversation_messages'),
    path('messages/<uuid:id>/', views.MessageDetailView.as_view(), name='message_detail'),
    path('messages/<uuid:message_id>/react/', views.MessageReactionView.as_view(), name='message_reaction'),
    path('messages/<uuid:message_id>/report/', views.ReportMessageView.as_view(), name='report_message'),
    
    # Participants
    path('conversations/<uuid:conversation_id>/participants/', views.ConversationParticipantsView.as_view(), name='conversation_participants'),
    path('conversations/<uuid:conversation_id>/participants/add/', views.AddParticipantView.as_view(), name='add_participant'),
    path('conversations/<uuid:conversation_id>/participants/<uuid:participant_id>/remove/', views.RemoveParticipantView.as_view(), name='remove_participant'),
    
    # Conversation Actions
    path('conversations/<uuid:conversation_id>/read/', views.mark_conversation_read, name='mark_conversation_read'),
    path('conversations/<uuid:conversation_id>/settings/', views.update_conversation_settings, name='update_conversation_settings'),
    
    # Blocking
    path('block/', views.BlockUserView.as_view(), name='block_user'),
    path('unblock/<uuid:user_id>/', views.UnblockUserView.as_view(), name='unblock_user'),
    path('blocked/', views.BlockedUsersListView.as_view(), name='blocked_users'),
    
    # Stats
    path('stats/', views.messaging_stats, name='messaging_stats'),
]
