from rest_framework import serializers
from .models import TechnicalDocument, DocumentChunk, CuratedQAKnowledge, CurationQueueItem


class TechnicalDocumentSerializer(serializers.ModelSerializer):
    chunksCount = serializers.SerializerMethodField()

    class Meta:
        model = TechnicalDocument
        fields = [
            'id', 'tenant_id', 'is_system_guide', 'category', 'title',
            'file_path', 'applicable_model', 'applicable_year_start',
            'applicable_year_end', 'serial_number_prefix', 'file_size_bytes',
            'is_active', 'created_at', 'chunksCount'
        ]

    def get_chunksCount(self, obj):
        return obj.chunks.count()


class CuratedQAKnowledgeSerializer(serializers.ModelSerializer):
    approvedByName = serializers.SerializerMethodField()

    class Meta:
        model = CuratedQAKnowledge
        fields = [
            'id', 'tenant_id', 'is_system_guide', 'category',
            'question_pattern', 'gold_answer', 'applicable_model',
            'applicable_year_start', 'applicable_year_end',
            'approved_by', 'approvedByName', 'upvote_count',
            'downvote_count', 'created_at'
        ]

    def get_approvedByName(self, obj):
        return obj.approved_by.username if obj.approved_by else None


class CurationQueueItemSerializer(serializers.ModelSerializer):
    userName = serializers.SerializerMethodField()
    reviewedByName = serializers.SerializerMethodField()

    class Meta:
        model = CurationQueueItem
        fields = [
            'id', 'tenant_id', 'user', 'userName', 'user_query',
            'generated_answer', 'technician_feedback', 'vote_type',
            'status', 'reviewed_by', 'reviewedByName', 'curated_answer',
            'created_at', 'reviewed_at'
        ]

    def get_userName(self, obj):
        return obj.user.username if obj.user else 'Kỹ thuật viên'

    def get_reviewedByName(self, obj):
        return obj.reviewed_by.username if obj.reviewed_by else None
