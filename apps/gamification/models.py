"""
Gamification models for Campus Club Management Suite
Points, badges, achievements, leaderboards, and engagement tracking
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid

class PointsCategory(models.Model):
    """Categories for different types of points"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default="#007bff")
    is_active = models.BooleanField(default=True)
    
    # Point values
    base_points = models.IntegerField(default=10, validators=[MinValueValidator(1)])
    multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=1.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'points_categories'
        verbose_name = 'Points Category'
        verbose_name_plural = 'Points Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Badge(models.Model):
    """Achievement badges users can earn"""
    
    DIFFICULTY_CHOICES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
        ('diamond', 'Diamond'),
    ]
    
    BADGE_TYPES = [
        ('activity', 'Activity Badge'),
        ('milestone', 'Milestone Badge'),
        ('social', 'Social Badge'),
        ('leadership', 'Leadership Badge'),
        ('academic', 'Academic Badge'),
        ('special', 'Special Badge'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    badge_type = models.CharField(max_length=20, choices=BADGE_TYPES, default='activity')
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='bronze')
    
    # Visual
    icon = models.ImageField(upload_to='badges/', blank=True, null=True)
    icon_url = models.URLField(blank=True)
    color = models.CharField(max_length=7, default="#007bff")
    
    # Requirements
    requirements = models.JSONField(default=dict, blank=True, help_text="Requirements to earn this badge")
    points_reward = models.IntegerField(default=100, validators=[MinValueValidator(0)])
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_hidden = models.BooleanField(default=False, help_text="Hidden until earned")
    is_repeatable = models.BooleanField(default=False)
    
    # Statistics
    total_earned = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'badges'
        verbose_name = 'Badge'
        verbose_name_plural = 'Badges'
        ordering = ['difficulty', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_difficulty_display()})"
    
    @property
    def rarity_percentage(self):
        """Calculate how rare this badge is"""
        from apps.authentication.models import User
        total_users = User.objects.filter(is_active=True).count()
        if total_users == 0:
            return 0
        return round((self.total_earned / total_users) * 100, 2)


class UserPoints(models.Model):
    """User's points tracking"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='points_profile')
    
    # Point totals
    total_points = models.IntegerField(default=0)
    lifetime_points = models.IntegerField(default=0)
    
    # Category breakdowns
    activity_points = models.IntegerField(default=0)
    social_points = models.IntegerField(default=0)
    leadership_points = models.IntegerField(default=0)
    academic_points = models.IntegerField(default=0)
    special_points = models.IntegerField(default=0)
    
    # Rankings
    global_rank = models.IntegerField(default=0)
    college_rank = models.IntegerField(default=0)
    
    # Streaks
    current_streak = models.IntegerField(default=0, help_text="Current consecutive days with activity")
    longest_streak = models.IntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    
    # Level system
    level = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    experience_points = models.IntegerField(default=0)
    points_to_next_level = models.IntegerField(default=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_points'
        verbose_name = 'User Points'
        verbose_name_plural = 'User Points'
        ordering = ['-total_points']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.total_points} points"
    
    def add_points(self, points, category='activity', description=""):
        """Add points to user account"""
        self.total_points += points
        self.lifetime_points += points
        self.experience_points += points
        
        # Update category points
        category_field = f"{category}_points"
        if hasattr(self, category_field):
            current_value = getattr(self, category_field)
            setattr(self, category_field, current_value + points)
        
        # Check for level up
        self._check_level_up()
        
        # Update streak
        self._update_streak()
        
        self.save()
        
        # Create points transaction record
        PointsTransaction.objects.create(
            user=self.user,
            points=points,
            transaction_type='earned',
            category=category,
            description=description
        )
        
        # Check for badge achievements
        self._check_badge_achievements()
    
    def deduct_points(self, points, reason=""):
        """Deduct points (for penalties or spending)"""
        if points > self.total_points:
            points = self.total_points
        
        self.total_points -= points
        self.save()
        
        PointsTransaction.objects.create(
            user=self.user,
            points=-points,
            transaction_type='spent',
            description=reason
        )
    
    def _check_level_up(self):
        """Check if user should level up"""
        while self.experience_points >= self.points_to_next_level:
            self.experience_points -= self.points_to_next_level
            self.level += 1
            self.points_to_next_level = self._calculate_next_level_requirement()
            
            # Award level up bonus
            level_bonus = self.level * 50
            self.total_points += level_bonus
            
            # Create level up transaction
            PointsTransaction.objects.create(
                user=self.user,
                points=level_bonus,
                transaction_type='level_bonus',
                description=f"Level {self.level} bonus"
            )
    
    def _calculate_next_level_requirement(self):
        """Calculate points needed for next level"""
        return 100 + (self.level - 1) * 50
    
    def _update_streak(self):
        """Update activity streak"""
        today = timezone.now().date()
        
        if self.last_activity_date:
            if self.last_activity_date == today:
                return  # Already updated today
            elif self.last_activity_date == today - timezone.timedelta(days=1):
                self.current_streak += 1
            else:
                self.current_streak = 1
        else:
            self.current_streak = 1
        
        self.last_activity_date = today
        
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
    
    def _check_badge_achievements(self):
        """Check if user has earned any new badges"""
        from .utils import check_user_badges
        check_user_badges(self.user)


class UserBadge(models.Model):
    """Badges earned by users"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='earned_badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='earned_by')
    
    # Earning details
    earned_at = models.DateTimeField(auto_now_add=True)
    earned_for = models.TextField(blank=True, help_text="What activity earned this badge")
    
    # Display settings
    is_featured = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'user_badges'
        verbose_name = 'User Badge'
        verbose_name_plural = 'User Badges'
        unique_together = ['user', 'badge']
        ordering = ['-earned_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.badge.name}"


class PointsTransaction(models.Model):
    """Points transaction history"""
    
    TRANSACTION_TYPES = [
        ('earned', 'Points Earned'),
        ('spent', 'Points Spent'),
        ('bonus', 'Bonus Points'),
        ('penalty', 'Penalty'),
        ('level_bonus', 'Level Up Bonus'),
        ('badge_reward', 'Badge Reward'),
        ('streak_bonus', 'Streak Bonus'),
        ('adjustment', 'Admin Adjustment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='points_transactions')
    
    points = models.IntegerField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    category = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    
    # Related objects
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.UUIDField(null=True, blank=True)
    
    # Balance after transaction
    balance_after = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'points_transactions'
        verbose_name = 'Points Transaction'
        verbose_name_plural = 'Points Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'transaction_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.full_name} - {self.points} points ({self.get_transaction_type_display()})"


class Achievement(models.Model):
    """Long-term achievements and goals"""
    
    ACHIEVEMENT_TYPES = [
        ('milestone', 'Milestone Achievement'),
        ('challenge', 'Challenge Achievement'),
        ('seasonal', 'Seasonal Achievement'),
        ('special', 'Special Achievement'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    description = models.TextField()
    achievement_type = models.CharField(max_length=20, choices=ACHIEVEMENT_TYPES, default='milestone')
    
    # Requirements and rewards
    requirements = models.JSONField(default=dict, help_text="Requirements to complete achievement")
    points_reward = models.IntegerField(default=500)
    badge_reward = models.ForeignKey(Badge, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Timing
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Progress tracking
    total_participants = models.IntegerField(default=0)
    total_completed = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'achievements'
        verbose_name = 'Achievement'
        verbose_name_plural = 'Achievements'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def completion_rate(self):
        """Calculate completion rate percentage"""
        if self.total_participants == 0:
            return 0
        return round((self.total_completed / self.total_participants) * 100, 2)
    
    @property
    def is_available(self):
        """Check if achievement is currently available"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        
        if self.end_date and now > self.end_date:
            return False
        
        return True


class UserAchievement(models.Model):
    """User's progress on achievements"""
    
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name='user_progress')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    progress = models.JSONField(default=dict, help_text="Progress tracking data")
    progress_percentage = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'user_achievements'
        verbose_name = 'User Achievement'
        verbose_name_plural = 'User Achievements'
        unique_together = ['user', 'achievement']
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.achievement.name} ({self.progress_percentage}%)"
    
    def update_progress(self, progress_data):
        """Update achievement progress"""
        self.progress.update(progress_data)
        
        # Calculate progress percentage based on requirements
        # This would be implemented based on specific achievement logic
        self._calculate_progress_percentage()
        
        if self.progress_percentage >= 100:
            self.complete_achievement()
        
        self.save()
    
    def complete_achievement(self):
        """Mark achievement as completed and award rewards"""
        if self.status != 'completed':
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.progress_percentage = 100
            
            # Award points
            if self.achievement.points_reward > 0:
                points_profile, created = UserPoints.objects.get_or_create(user=self.user)
                points_profile.add_points(
                    self.achievement.points_reward,
                    category='special',
                    description=f"Achievement completed: {self.achievement.name}"
                )
            
            # Award badge if specified
            if self.achievement.badge_reward:
                UserBadge.objects.get_or_create(
                    user=self.user,
                    badge=self.achievement.badge_reward,
                    defaults={'earned_for': f"Achievement: {self.achievement.name}"}
                )
            
            # Update achievement stats
            self.achievement.total_completed += 1
            self.achievement.save()
    
    def _calculate_progress_percentage(self):
        """Calculate progress percentage based on requirements"""
        # This would be implemented based on specific achievement requirements
        # For now, we'll use a simple calculation
        requirements = self.achievement.requirements
        if not requirements:
            return
        
        total_requirements = len(requirements)
        completed_requirements = 0
        
        for req_key, req_value in requirements.items():
            if req_key in self.progress:
                if isinstance(req_value, (int, float)):
                    if self.progress[req_key] >= req_value:
                        completed_requirements += 1
                else:
                    if self.progress[req_key]:
                        completed_requirements += 1
        
        if total_requirements > 0:
            self.progress_percentage = int((completed_requirements / total_requirements) * 100)


class Leaderboard(models.Model):
    """Leaderboard configurations"""
    
    LEADERBOARD_TYPES = [
        ('points', 'Points Leaderboard'),
        ('level', 'Level Leaderboard'),
        ('badges', 'Badge Count Leaderboard'),
        ('activity', 'Activity Leaderboard'),
        ('streak', 'Streak Leaderboard'),
    ]
    
    TIME_PERIODS = [
        ('all_time', 'All Time'),
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    leaderboard_type = models.CharField(max_length=20, choices=LEADERBOARD_TYPES, default='points')
    time_period = models.CharField(max_length=20, choices=TIME_PERIODS, default='all_time')
    
    # Filtering
    college_specific = models.BooleanField(default=False)
    club_specific = models.BooleanField(default=False)
    
    # Display settings
    is_active = models.BooleanField(default=True)
    show_top_n = models.IntegerField(default=100, validators=[MinValueValidator(10)])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'leaderboards'
        verbose_name = 'Leaderboard'
        verbose_name_plural = 'Leaderboards'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_leaderboard_type_display()})"
    
    def get_leaderboard_data(self, college=None, club=None, limit=None):
        """Get leaderboard data based on configuration"""
        from apps.authentication.models import User
        
        # Base queryset
        users = User.objects.filter(is_active=True).select_related('points_profile')
        
        # Apply filters
        if self.college_specific and college:
            users = users.filter(college_email_domain=college.domain)
        
        if self.club_specific and club:
            users = users.filter(
                joined_clubs__memberships__club=club,
                joined_clubs__memberships__status='active'
            )
        
        # Time period filtering
        if self.time_period != 'all_time':
            now = timezone.now()
            if self.time_period == 'daily':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif self.time_period == 'weekly':
                start_date = now - timezone.timedelta(days=now.weekday())
            elif self.time_period == 'monthly':
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Filter points transactions for time period
            # This would require more complex querying for time-based leaderboards
        
        # Ordering based on type
        if self.leaderboard_type == 'points':
            users = users.order_by('-points_profile__total_points')
        elif self.leaderboard_type == 'level':
            users = users.order_by('-points_profile__level', '-points_profile__experience_points')
        elif self.leaderboard_type == 'badges':
            users = users.annotate(badge_count=models.Count('earned_badges')).order_by('-badge_count')
        elif self.leaderboard_type == 'streak':
            users = users.order_by('-points_profile__current_streak', '-points_profile__longest_streak')
        
        # Apply limit
        limit = limit or self.show_top_n
        users = users[:limit]
        
        return users


# Signal handlers
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_points_profile(sender, instance, created, **kwargs):
    """Create points profile for new users"""
    if created:
        UserPoints.objects.get_or_create(user=instance)

@receiver(post_save, sender=UserBadge)
def update_badge_stats(sender, instance, created, **kwargs):
    """Update badge statistics when earned"""
    if created:
        badge = instance.badge
        badge.total_earned += 1
        badge.save()
        
        # Award badge points
        points_profile, created = UserPoints.objects.get_or_create(user=instance.user)
        points_profile.add_points(
            badge.points_reward,
            category='special',
            description=f"Badge earned: {badge.name}"
        )
