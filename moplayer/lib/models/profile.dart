import '../core/utils/json_x.dart';

/// A Supabase user profile row (mirrors the `profiles` table).
class Profile {
  const Profile({
    required this.id,
    this.username,
    this.displayName,
    this.avatarUrl,
    this.role = 'user',
    this.createdAt,
  });

  final String id;
  final String? username;
  final String? displayName;
  final String? avatarUrl;
  final String role;
  final DateTime? createdAt;

  bool get isAdmin => role == 'admin';

  factory Profile.fromJson(Map<String, dynamic> json) => Profile(
    id: JsonX.asString(json['id']),
    username: JsonX.asStringOrNull(json['username']),
    displayName: JsonX.asStringOrNull(json['display_name']),
    avatarUrl: JsonX.asStringOrNull(json['avatar_url']),
    role: JsonX.asString(json['role'], fallback: 'user'),
    createdAt: DateTime.tryParse(JsonX.asString(json['created_at'])),
  );
}
