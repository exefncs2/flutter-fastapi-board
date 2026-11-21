import 'package:flutter/foundation.dart';
import '../models/post.dart';
import '../services/api_service.dart';

/// 留言提供者，管理留言板的資料和操作
class PostProvider with ChangeNotifier {
  List<Post> _posts = [];
  bool _isLoading = false;
  String? _error;
  final ApiService _apiService;

  /// 構造函式，接收API服務實例
  PostProvider(this._apiService);

  // 取得器
  List<Post> get posts => _posts;
  bool get isLoading => _isLoading;
  String? get error => _error;

  /// 載入所有留言
  Future<void> loadPosts() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _posts = await _apiService.getPosts();
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
    }
  }

  /// 建立新留言
  Future<void> createPost(String content) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final newPost = await _apiService.createPost(content);
      _posts.insert(0, newPost); // 將新留言新增到列表頂部
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
    }
  }

  /// 新增評論到留言
  Future<void> addComment(int postId, String content) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final newComment = await _apiService.addComment(postId, content);
      
      // 查找對應留言並新增評論
      final postIndex = _posts.indexWhere((post) => post.id == postId);
      if (postIndex != -1) {
        final post = _posts[postIndex];
        final updatedComments = List<Comment>.from(post.comments)..add(newComment);
        
        // 建立帶有更新評論的新留言物件
        final updatedPost = Post(
          id: post.id,
          username: post.username,
          content: post.content,
          timestamp: post.timestamp,
          comments: updatedComments,
        );
        
        // 更新留言列表
        _posts[postIndex] = updatedPost;
      }
      
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
    }
  }
}