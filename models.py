from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

# ============================================================================
# AUTHENTICATION & USER MANAGEMENT
# ============================================================================

class Role(models.Model):
    """Model untuk roles (Admin, Contributor, User)"""
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    
    class Meta:
        db_table = 'roles'
        managed = False  # Karena tabel sudah ada di SQL Server
    
    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    """Custom user manager"""
    def create_user(self, email, name, password=None, role_id=3):
        if not email:
            raise ValueError('Users must have an email address')
        user = self.model(
            email=self.normalize_email(email),
            name=name,
            role_id=role_id
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, name, password):
        user = self.create_user(email, name, password, role_id=1)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """Model untuk users"""
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255, unique=True)
    password = models.CharField(max_length=255)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, db_column='role_id')
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    
    class Meta:
        db_table = 'users'
        managed = False
    
    def __str__(self):
        return self.email


# ============================================================================
# MASTER SHOWS & GENRES
# ============================================================================

class MasterShows(models.Model):
    """Model untuk Master_Shows - tabel utama lost media"""
    show_id = models.AutoField(primary_key=True, db_column='Show_ID')
    title = models.TextField(db_column='Title')
    release_year = models.IntegerField(null=True, db_column='ReleaseYear')
    first_source_table = models.CharField(max_length=20, null=True, db_column='First_Source_Table')
    first_source_id = models.CharField(max_length=20, null=True, db_column='First_Source_ID')
    
    class Meta:
        db_table = 'Master_Shows'
        managed = False
    
    def __str__(self):
        return f"{self.title} ({self.release_year})"


class ListGenre(models.Model):
    """Model untuk list_genre"""
    genre_id = models.AutoField(primary_key=True)
    genre_name = models.CharField(max_length=100)
    
    class Meta:
        db_table = 'list_genre'
        managed = False
    
    def __str__(self):
        return self.genre_name


class ShowGenreMapping(models.Model):
    """Model untuk Show_Genre_Mapping - relasi many-to-many"""
    show = models.ForeignKey(MasterShows, on_delete=models.CASCADE, db_column='Show_ID')
    genre = models.ForeignKey(ListGenre, on_delete=models.CASCADE, db_column='genre_id')
    
    class Meta:
        db_table = 'Show_Genre_Mapping'
        managed = False
        unique_together = ('show', 'genre')


# ============================================================================
# MEDIA STATUS & POPULARITY
# ============================================================================

class MediaStatusLog(models.Model):
    """Model untuk Media_StatusLog - tracking status recovery"""
    show = models.OneToOneField(MasterShows, on_delete=models.CASCADE, 
                                 primary_key=True, db_column='Show_ID')
    recovery_status = models.CharField(max_length=50, 
                                       choices=[
                                           ('Founded', 'Founded'),
                                           ('Fully Lost', 'Fully Lost'),
                                           ('Partial Found', 'Partial Found')
                                       ])
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'Media_StatusLog'
        managed = False
    
    def __str__(self):
        return f"{self.show.title} - {self.recovery_status}"


class MediaPopularity(models.Model):
    """Model untuk MediaPopularity - tracking pencarian"""
    id = models.OneToOneField(MasterShows, on_delete=models.CASCADE, 
                              primary_key=True, db_column='ID')
    search_count = models.IntegerField(default=0, db_column='SearchCount')
    
    class Meta:
        db_table = 'MediaPopularity'
        managed = False


# ============================================================================
# CATEGORIES & ARTICLES
# ============================================================================

class Category(models.Model):
    """Model untuk categories"""
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=255, unique=True)
    
    class Meta:
        db_table = 'categories'
        managed = False
        verbose_name_plural = 'categories'
    
    def __str__(self):
        return self.name


class Article(models.Model):
    """Model untuk articles"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ]
    
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=500)
    content = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='draft')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, db_column='category_id')
    show = models.ForeignKey(MasterShows, on_delete=models.SET_NULL, 
                            null=True, blank=True, db_column='show_id')
    tconst = models.CharField(max_length=15, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    class Meta:
        db_table = 'articles'
        managed = False
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class MediaFile(models.Model):
    """Model untuk media_files"""
    RECOVERY_STATUS_CHOICES = [
        ('Found', 'Found'),
        ('Partially_Found', 'Partially Found'),
        ('Fully_Lost', 'Fully Lost')
    ]
    
    id = models.AutoField(primary_key=True)
    article = models.ForeignKey(Article, on_delete=models.CASCADE, 
                               db_column='article_id', related_name='media_files')
    file_path = models.CharField(max_length=1000)
    file_type = models.CharField(max_length=100, null=True, blank=True)
    original_name = models.CharField(max_length=500)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                    null=True, blank=True, db_column='uploaded_by_user_id')
    recovery_status = models.CharField(max_length=50, choices=RECOVERY_STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'media_files'
        managed = False


# ============================================================================
# IMDB TABLES (Read-only reference)
# ============================================================================

class TitleBasics(models.Model):
    """Model untuk title_basics dari IMDb"""
    tconst = models.CharField(max_length=15, primary_key=True)
    title_type = models.TextField(null=True, db_column='titleType')
    primary_title = models.TextField(null=True, db_column='primaryTitle')
    original_title = models.TextField(null=True, db_column='originalTitle')
    is_adult = models.TextField(null=True, db_column='isAdult')
    start_year = models.IntegerField(null=True, db_column='startYear')
    end_year = models.IntegerField(null=True, db_column='endYear')
    runtime_minutes = models.IntegerField(null=True, db_column='runtimeMinutes')
    
    class Meta:
        db_table = 'title_basics'
        managed = False
    
    def __str__(self):
        return f"{self.primary_title} ({self.start_year})"


class TitleRatings(models.Model):
    """Model untuk title_ratings dari IMDb"""
    tconst = models.OneToOneField(TitleBasics, on_delete=models.CASCADE, 
                                  primary_key=True, db_column='tconst')
    average_rating = models.TextField(null=True, db_column='averageRating')
    num_votes = models.TextField(null=True, db_column='numVotes')
    
    class Meta:
        db_table = 'title_ratings'
        managed = False


# ============================================================================
# TV SHOW TABLES (Read-only reference)
# ============================================================================

class Shows(models.Model):
    """Model untuk shows dari TV_Show database"""
    show_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255, null=True)
    number_of_seasons = models.IntegerField(null=True)
    number_of_episodes = models.IntegerField(null=True)
    overview = models.TextField(null=True)
    adult = models.BooleanField(null=True)
    in_production = models.BooleanField(null=True)
    original_name = models.CharField(max_length=255, null=True)
    popularity = models.FloatField(null=True)
    tagline = models.CharField(max_length=255, null=True)
    eposide_run_time = models.IntegerField(null=True)
    type_id = models.IntegerField(null=True)
    status_id = models.IntegerField(null=True)
    
    class Meta:
        db_table = 'shows'
        managed = False
    
    def __str__(self):
        return self.name or f"Show {self.show_id}"


class ShowVotes(models.Model):
    """Model untuk show_votes"""
    vote_count = models.IntegerField(null=True)
    vote_average = models.FloatField(null=True)
    show = models.ForeignKey(Shows, on_delete=models.CASCADE, db_column='show_id')
    
    class Meta:
        db_table = 'show_votes'
        managed = False