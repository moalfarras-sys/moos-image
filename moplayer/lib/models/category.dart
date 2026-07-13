import '../core/utils/json_x.dart';

/// A content category (channel group / VOD genre / series genre).
class Category {
  const Category({
    required this.id,
    required this.name,
    this.parentId,
    this.count,
  });

  final String id;
  final String name;
  final String? parentId;

  /// Optional number of items in this category (used by M3U groups).
  final int? count;

  /// A synthetic "All" category used at the top of every list.
  static const String allId = '__all__';
  static const String favoritesId = '__favorites__';

  factory Category.fromXtream(Map<String, dynamic> json) {
    return Category(
      id: JsonX.asString(json['category_id']),
      name: JsonX.asString(json['category_name'], fallback: 'Unknown'),
      parentId: JsonX.asStringOrNull(json['parent_id']),
    );
  }

  Category copyWith({int? count}) => Category(
    id: id,
    name: name,
    parentId: parentId,
    count: count ?? this.count,
  );

  @override
  bool operator ==(Object other) =>
      other is Category && other.id == id && other.name == name;

  @override
  int get hashCode => Object.hash(id, name);
}
